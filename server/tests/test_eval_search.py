"""Random search: sampling, hashing, constraints, winner selection, freeze."""

from __future__ import annotations

import random
from datetime import date
from typing import Any

from api_factories import make_club_seasons, make_league_seasons, make_store, make_transitions

from app.services.constants import DEFAULT_RETRIEVAL
from pipeline.eval.candidates import (
    SUPERSET_AGE_BAND,
    SUPERSET_DEST_STRENGTH_BAND,
    SUPERSET_VALUE_BRACKET,
)
from pipeline.eval.search import (
    MIN_POOL_TARGET_RANGE,
    POOL_K_RANGE,
    WEIGHT_RANGE,
    SearchResult,
    Trial,
    config_hash,
    render_constants_snippet,
    run_search,
    sample_config,
    select_winner,
)


def test_sampling_is_deterministic_per_seed() -> None:
    first = [sample_config(random.Random(42)) for _ in range(5)]
    second = [sample_config(random.Random(42)) for _ in range(5)]
    assert first == second
    assert first != [sample_config(random.Random(43)) for _ in range(5)]


def test_sampled_configs_respect_every_range_and_the_superset() -> None:
    rng = random.Random(1)
    for _ in range(200):
        config = sample_config(rng)
        for weight in (
            config.w_log_value,
            config.w_age,
            config.w_dest_strength,
            config.w_origin_strength,
            config.w_elo,
            config.w_dest_club_value,
            config.w_origin_club_value,
            config.w_minutes,
            config.w_sub_position,
            config.w_recency,
        ):
            assert WEIGHT_RANGE[0] <= weight <= WEIGHT_RANGE[1]
        assert POOL_K_RANGE[0] <= config.pool_k <= POOL_K_RANGE[1]
        assert MIN_POOL_TARGET_RANGE[0] <= config.min_pool_target <= MIN_POOL_TARGET_RANGE[1]
        base, *rest = config.ladder
        assert base.age_band < config.ladder[1].age_band <= SUPERSET_AGE_BAND
        assert rest[-1].origin_tier_band is None and rest[-1].drop_club_terms
        for step in config.ladder:
            assert step.value_bracket[0] >= SUPERSET_VALUE_BRACKET[0]
            assert step.value_bracket[1] <= SUPERSET_VALUE_BRACKET[1]
            assert step.value_bracket[0] <= base.value_bracket[0]
            assert step.value_bracket[1] >= base.value_bracket[1]
            assert step.dest_strength_band >= base.dest_strength_band
            assert step.dest_strength_band <= SUPERSET_DEST_STRENGTH_BAND
        # The band never shrinks along the ladder and widens at least once.
        bands = [step.dest_strength_band for step in config.ladder]
        assert bands == sorted(bands)
        assert bands[-1] > bands[0]


def test_config_hash_tracks_content_not_identity() -> None:
    sampled = sample_config(random.Random(3))
    again = sample_config(random.Random(3))
    assert config_hash(sampled) == config_hash(again)
    assert len(config_hash(sampled)) == 12
    assert config_hash(sampled) != config_hash(DEFAULT_RETRIEVAL)


def _trial(index: int, score: float, insufficient_rate: float, coverage: float) -> Trial:
    return Trial(
        index=index,
        config=DEFAULT_RETRIEVAL,
        digest="0" * 12,
        score=score,
        insufficient_rate=insufficient_rate,
        coverage=coverage,
    )


def test_select_winner_applies_the_constraints() -> None:
    trials = [
        _trial(0, 0.20, 0.05, 0.50),
        _trial(1, 0.10, 0.07, 0.50),  # refuses >1pt more than hand-set: out
        _trial(2, 0.11, 0.05, 0.70),  # coverage out of the sanity band: out
        _trial(3, 0.15, 0.06, 0.40),  # eligible and best
        _trial(4, 0.15, 0.05, 0.50),  # same score, higher index: loses the tie
    ]
    assert select_winner(trials).index == 3


def test_select_winner_falls_back_to_the_hand_set_config() -> None:
    trials = [_trial(0, 0.20, 0.05, 0.50), _trial(1, 0.10, 0.50, 0.50)]
    assert select_winner(trials).index == 0


def _tiny_store():  # type: ignore[no-untyped-def]
    query = {
        "player_id": 1,
        "season": 2020,
        "transfer_date": date(2020, 8, 1),
        "v_after_date": date(2021, 8, 1),
    }
    comps: list[dict[str, Any]] = [
        {
            "player_id": 100 + i,
            "season": 2018,
            "transfer_date": date(2018, 8, 1),
            "v_after_date": date(2019, 8, 1),
            "multiplier": 0.8 + 0.1 * i,
        }
        for i in range(6)
    ]
    return make_store(
        transitions=make_transitions([query, *comps]),
        league_seasons=make_league_seasons(
            [{"league": league, "season": 2020, "tier": 1} for league in ("AA1", "BB1")]
        ),
        club_seasons=make_club_seasons([{"club_id": 21, "season": 2020, "tercile": 2}]),
    )


def test_run_search_is_deterministic_and_scores_the_hand_set_first() -> None:
    store = _tiny_store()
    first = run_search(store, n_configs=2, seed=5)
    second = run_search(store, n_configs=2, seed=5)
    assert first.n_queries == 1
    assert len(first.trials) == 3
    assert first.trials[0].config == DEFAULT_RETRIEVAL
    assert [t.score for t in first.trials] == [t.score for t in second.trials]
    assert [t.digest for t in first.trials] == [t.digest for t in second.trials]
    assert first.winner.digest == second.winner.digest


def test_constants_snippet_carries_the_full_frozen_surface() -> None:
    trial = Trial(
        index=1,
        config=sample_config(random.Random(9)),
        digest="abcdef123456",
        score=0.1,
        insufficient_rate=0.01,
        coverage=0.5,
    )
    result = SearchResult(
        trials=[_trial(0, 0.2, 0.0, 0.5), trial],
        winner=trial,
        n_queries=100,
        n_skipped=2,
        seed=7,
    )
    snippet = render_constants_snippet(result, n_configs=300)
    for needle in (
        "abcdef123456",
        "MIN_POOL_TARGET",
        "LADDER",
        "POOL_K",
        "W_LOG_VALUE",
        "W_RECENCY",
        "LadderStep",
        "seed 7",
    ):
        assert needle in snippet
