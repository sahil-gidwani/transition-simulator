"""The real-service backtest loop: determinism, availability, refusals, skips."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Any

import polars as pl
import pytest
from api_factories import make_club_seasons, make_league_seasons, make_store, make_transitions

from app.repositories.store import DataStore
from app.services.constants import DEFAULT_RETRIEVAL
from pipeline.eval.records import RECORDS_SCHEMA
from pipeline.eval.runner import run_backtest

# One 2020 query (transfer 2020-08-01) plus five comps observable well before
# it. Factory defaults already conform (ATT, tier 1 -> tier 1, ~10M).
_QUERY_ROW: dict[str, Any] = {
    "player_id": 1,
    "player_name": "Query Player",
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


def _store(transitions: pl.DataFrame) -> DataStore:
    return make_store(
        transitions=transitions,
        league_seasons=make_league_seasons(
            [
                {"league": "AA1", "season": 2020, "tier": 1, "strength": 18.0},
                {"league": "BB1", "season": 2020, "tier": 1, "strength": 18.0},
                {"league": "AA1", "season": 2018, "tier": 1, "strength": 18.0},
                {"league": "BB1", "season": 2018, "tier": 1, "strength": 18.0},
            ]
        ),
        club_seasons=make_club_seasons([{"club_id": 21, "season": 2020, "tercile": 2}]),
    )


def _transitions(rows: list[dict[str, Any]]) -> pl.DataFrame:
    return make_transitions(rows)


def test_scored_query_records_engine_and_baselines() -> None:
    multipliers = [0.6, 0.9, 1.0, 1.2, 1.5]
    store = _store(
        _transitions(
            [_QUERY_ROW, *(_comp(100 + i, m) for i, m in enumerate(multipliers))],
        )
    )
    records, skips = run_backtest(store, (2020,))
    assert skips == []
    assert records.height == 1
    row = records.row(0, named=True)
    assert row["insufficient"] is False
    assert row["pool_size"] == 5
    assert row["n_available"] == 5
    assert row["q25"] <= row["q50"] <= row["q75"]
    assert row["actual_multiplier"] == pytest.approx(0.8)
    # Baselines are the plain quantiles of the five available multipliers.
    expected = pl.Series(multipliers)
    assert row["b1_q50"] == pytest.approx(expected.quantile(0.5, interpolation="linear"))
    assert row["b2_fallback"] is True  # bucket of 5 < MIN_BUCKET
    assert row["b2_q50"] == row["b1_q50"]
    assert sorted(row["pool_multipliers"]) == pytest.approx(multipliers)
    assert len(row["pool_similarities"]) == 5
    assert records.schema == pl.Schema(RECORDS_SCHEMA)


def test_two_runs_are_identical() -> None:
    store = _store(_transitions([_QUERY_ROW, *(_comp(100 + i, 0.8 + 0.1 * i) for i in range(6))]))
    first, _ = run_backtest(store, (2020,))
    second, _ = run_backtest(store, (2020,))
    assert first.equals(second)


def test_unobserved_outcomes_are_not_available_as_comps() -> None:
    # Both comps match perfectly, but one's v_after_date is after the query's
    # transfer date: only the observed one may enter the pool, leaving a
    # single comp - below MIN_COMPS_FOR_RANGE, so the engine must refuse.
    store = _store(
        _transitions(
            [
                _QUERY_ROW,
                _comp(100, 1.2),
                _comp(101, 5.0, v_after_date=date(2020, 9, 1)),  # observed AFTER t
            ]
        )
    )
    records, _ = run_backtest(store, (2020,))
    row = records.row(0, named=True)
    assert row["n_available"] == 1
    assert row["insufficient"] is True
    assert row["q25"] is None and row["q50"] is None and row["q75"] is None
    assert row["confidence"] == "insufficient"


def test_unbuildable_queries_are_counted_as_skips() -> None:
    bad_query = {
        **_QUERY_ROW,
        "player_id": 2,
        "to_league": None,
        "to_tier": None,
        "to_tercile": None,
    }
    store = _store(_transitions([_QUERY_ROW, bad_query, *(_comp(100 + i, 1.0) for i in range(3))]))
    records, skips = run_backtest(store, (2020,))
    assert records.height == 1
    assert [s.reason for s in skips] == ["null_to_league"]
    assert skips[0].player_id == 2


def test_league_level_ablation_withholds_the_destination_club() -> None:
    # The riser (multiplier 2.0) is the only comp whose destination-club
    # context clashes with the actual dest club (tercile 2, elo 0.75). With
    # the club selected it earns a lower similarity weight, pulling q75 down;
    # in the league-only ablation all three comps tie.
    comps = [
        _comp(100, 1.0, to_tercile=2, to_elo_pct=0.75),
        _comp(101, 2.0, to_tercile=3, to_elo_pct=0.25),
        _comp(102, 1.0, to_tercile=2, to_elo_pct=0.75),
    ]
    store = _store(_transitions([_QUERY_ROW, *comps]))
    # A fixed pool target keeps the ladder off the drop-club level regardless
    # of what the tuned serving default is.
    config = replace(DEFAULT_RETRIEVAL, min_pool_target=3)
    club_row = run_backtest(store, (2020,), config=config, club_level=True)[0].row(0, named=True)
    league_row = run_backtest(store, (2020,), config=config, club_level=False)[0].row(0, named=True)
    assert club_row["insufficient"] is False
    assert league_row["insufficient"] is False
    assert league_row["q75"] == pytest.approx(1.75)  # equal weights: hand-computed
    assert club_row["q75"] < league_row["q75"]
