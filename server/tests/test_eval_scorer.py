"""Parity: the numpy tuning scorer must reproduce the real serving engine."""

from __future__ import annotations

import random
from dataclasses import replace
from datetime import date
from typing import Any

import numpy as np
import pytest
from api_factories import make_club_seasons, make_league_seasons, make_store, make_transitions

from app.repositories.store import DataStore
from app.services import constants
from app.services.comps import find_comps
from app.services.constants import DEFAULT_RETRIEVAL, RetrievalConfig
from app.services.valuation import summarize_pool, weighted_quantile
from pipeline.eval.availability import available_universe
from pipeline.eval.candidates import candidate_set
from pipeline.eval.contexts import EvalQuery, build_eval_query
from pipeline.eval.scorer import np_weighted_quantile, score_query, selected_pool
from pipeline.eval.search import sample_config

_QUERY_ROW: dict[str, Any] = {
    "player_id": 1,
    "season": 2020,
    "transfer_date": date(2020, 8, 1),
    "v_before": 10_000_000,
    "v_after": 8_000_000,
    "multiplier": 0.8,
    "delta_pct": -0.2,
    "v_before_date": date(2020, 7, 1),
    "v_after_date": date(2021, 8, 1),
}


def _comp(player_id: int, multiplier: float, **overrides: Any) -> dict[str, Any]:
    return {
        "player_id": player_id,
        "season": 2018,
        "transfer_date": date(2018, 8, 1),
        "v_after_date": date(2019, 8, 1),
        "multiplier": multiplier,
        "v_after": int(10_000_000 * multiplier),
        "delta_pct": multiplier - 1.0,
        **overrides,
    }


# Every null policy, filter edge and ladder level the engine implements.
_UNIVERSE_ROWS: list[dict[str, Any]] = [
    _QUERY_ROW,
    _comp(100, 1.2),
    _comp(101, 0.7, age_at_transfer=None),  # null comp age: fails every age band
    _comp(102, 1.5, sub_position=None),  # neutral sub-position term
    _comp(103, 0.9, from_tercile=None, minutes_share_pre=None),  # dropped terms
    _comp(104, 1.1, to_elo_pct=None, to_elo=None),  # null comp elo
    _comp(105, 1.3, v_before=4_000_000),  # exact 0.4x bracket edge
    _comp(106, 0.8, v_before=30_000_000),  # 3.0x: widened bracket only
    _comp(107, 1.4, age_at_transfer=29.5),  # wide age band only
    _comp(108, 0.95, from_tier=3),  # origin tier +/-2 only
    _comp(109, 1.05, from_tier=None, from_league=None, from_tercile=None),  # last level only
    _comp(110, 1.25, from_league="ZZ9"),  # no strength row: term drops
    _comp(111, 1.15, transfer_date=date(2019, 2, 1), v_after_date=date(2020, 2, 1)),
    _comp(112, 1.0),  # identical twins: the player_id
    _comp(113, 1.0),  # tie-break must match
]


def _store() -> DataStore:
    leagues = [
        {"league": league, "season": season, "tier": 1, "strength": strength}
        for league, strength in (("AA1", 18.0), ("BB1", 17.4))
        for season in (2018, 2020)
    ]
    return make_store(
        transitions=make_transitions(_UNIVERSE_ROWS),
        league_seasons=make_league_seasons(leagues),
        club_seasons=make_club_seasons(
            [{"club_id": 21, "season": 2020, "tercile": 2, "elo_pct": 0.75}]
        ),
    )


def _built(store: DataStore) -> EvalQuery:
    row = store.transitions.comps_universe.filter(
        store.transitions.comps_universe["player_id"] == 1
    ).row(0, named=True)
    built = build_eval_query(row, store.seasons)
    assert isinstance(built, EvalQuery)
    return built


_CONFIGS: list[RetrievalConfig] = [
    DEFAULT_RETRIEVAL,
    replace(DEFAULT_RETRIEVAL, pool_k=3, w_minutes=1.3, w_age=0.2, w_elo=0.9),
    replace(DEFAULT_RETRIEVAL, min_pool_target=20),  # exhausts the ladder: drop-club level
    sample_config(random.Random(7)),  # sampled geometry: custom bands and k
]


@pytest.mark.parametrize("config_index", range(len(_CONFIGS)))
def test_numpy_pool_and_quantiles_match_the_real_service(config_index: int) -> None:
    config = _CONFIGS[config_index]
    store = _store()
    built = _built(store)
    universe = store.transitions.comps_universe
    strengths = store.seasons.strength_frame()
    universe_t = available_universe(universe, built.transfer_date)

    result = find_comps(
        built.query, built.dest_league, built.dest_club, universe_t, strengths, 2012, config=config
    )
    value_range, _ = summarize_pool(
        result.pool, built.query.value_eur, result.quality.relaxation_level
    )
    cands = candidate_set(built, universe, strengths, 2012)
    selection, similarities, level = selected_pool(cands, config)
    quantiles = score_query(cands, config)

    assert list(cands.player_id[selection]) == [c.player_id for c in result.pool]
    assert similarities == pytest.approx([c.similarity for c in result.pool], abs=1e-9)
    assert level == result.quality.relaxation_level
    assert value_range is not None and quantiles is not None
    assert quantiles == pytest.approx(
        (
            value_range.q25_multiplier,
            value_range.q50_multiplier,
            value_range.q75_multiplier,
        ),
        abs=1e-9,
    )


def test_refusal_parity_on_a_starved_universe() -> None:
    store = make_store(
        transitions=make_transitions([_QUERY_ROW, _comp(100, 1.2)]),
        league_seasons=make_league_seasons(
            [{"league": league, "season": 2020, "tier": 1} for league in ("AA1", "BB1")]
        ),
        club_seasons=make_club_seasons([{"club_id": 21, "season": 2020, "tercile": 2}]),
    )
    built = _built(store)
    universe = store.transitions.comps_universe
    strengths = store.seasons.strength_frame()
    universe_t = available_universe(universe, built.transfer_date)

    result = find_comps(
        built.query, built.dest_league, built.dest_club, universe_t, strengths, 2012
    )
    value_range, _ = summarize_pool(
        result.pool, built.query.value_eur, result.quality.relaxation_level
    )
    cands = candidate_set(built, universe, strengths, 2012)
    assert value_range is None
    assert score_query(cands, DEFAULT_RETRIEVAL) is None


def test_parity_survives_a_nonzero_calibration_shift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A future thresholds freeze may set CAL_SHIFT_* != 0; the numpy twin must
    # mirror summarize_pool's tier-shifted endpoints or the tune stage's
    # parity gate would refuse to run.
    monkeypatch.setattr(constants, "CAL_SHIFT_LOW", 0.1)
    monkeypatch.setattr(constants, "CAL_SHIFT_MEDIUM", 0.05)
    store = _store()
    built = _built(store)
    universe = store.transitions.comps_universe
    strengths = store.seasons.strength_frame()
    universe_t = available_universe(universe, built.transfer_date)

    result = find_comps(
        built.query, built.dest_league, built.dest_club, universe_t, strengths, 2012
    )
    value_range, confidence = summarize_pool(
        result.pool, built.query.value_eur, result.quality.relaxation_level
    )
    cands = candidate_set(built, universe, strengths, 2012)
    quantiles = score_query(cands, DEFAULT_RETRIEVAL)
    assert value_range is not None and quantiles is not None
    assert confidence in ("low", "medium")  # a shifted tier: the test must exercise one
    assert quantiles == pytest.approx(
        (
            value_range.q25_multiplier,
            value_range.q50_multiplier,
            value_range.q75_multiplier,
        ),
        abs=1e-9,
    )


def test_np_weighted_quantile_matches_serving_math() -> None:
    rng = random.Random(0)
    for _ in range(50):
        n = rng.randint(2, 12)
        values = [rng.uniform(0.2, 3.0) for _ in range(n)]
        weights = [rng.uniform(0.01, 1.0) for _ in range(n)]
        for q in (0.1, 0.25, 0.5, 0.75, 0.9):
            expected = weighted_quantile(values, weights, q)
            got = np_weighted_quantile(np.array(values), np.array(weights), q)
            assert got == pytest.approx(expected, abs=1e-12)
