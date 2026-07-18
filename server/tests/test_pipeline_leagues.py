import math
from typing import Any

import polars as pl
import pytest
from factories import make_competitions

from pipeline.transforms.leagues import assign_display_tiers, league_seasons

_NO_LABELS = make_competitions([])

# Test thresholds sized for small squad-value fixtures (ln of 1-8M ~ 13.8-15.9).
_T = (15.5, 14.5, 13.5)


def _strengths(rows: list[tuple[str, int, float | None]]) -> pl.DataFrame:
    return pl.DataFrame(
        rows,
        schema={"league": pl.String, "season": pl.Int64, "strength": pl.Float64},
        orient="row",
    )


def _tier_by_season(frame: pl.DataFrame, **kwargs: Any) -> list[int | None]:
    out = assign_display_tiers(frame, _T, **kwargs).sort("season")
    return out["tier"].to_list()


_CLUB_SEASONS_DEFAULTS: dict[str, Any] = {
    "club_id": 1,
    "season": 2020,
    "club_name": "Club",
    "league": "AA1",
    "league_source": "snapshot",
    "squad_value_eur": 1_000_000,
    "n_valued_players": 1,
    "tercile": 1,
}
_CLUB_SEASONS_SCHEMA: dict[str, pl.DataType | type[pl.DataType]] = {
    "club_id": pl.Int64,
    "season": pl.Int64,
    "club_name": pl.String,
    "league": pl.String,
    "league_source": pl.String,
    "squad_value_eur": pl.Int64,
    "n_valued_players": pl.Int64,
    "tercile": pl.Int8,
}


def _club_seasons(rows: list[dict[str, Any]], *, with_elo: bool = False) -> pl.DataFrame:
    defaults = dict(_CLUB_SEASONS_DEFAULTS)
    schema = dict(_CLUB_SEASONS_SCHEMA)
    if with_elo:
        defaults |= {"elo": None, "elo_mapped": False}
        schema |= {"elo": pl.Float64, "elo_mapped": pl.Boolean}
    return pl.DataFrame([{**defaults, **row} for row in rows], schema=schema)


def test_fixed_thresholds_map_strength_with_boundary_equality() -> None:
    frame = _strengths(
        [("A", 2020, 15.5), ("B", 2020, 15.49), ("C", 2020, 14.5), ("D", 2020, 13.49)]
    )
    out = assign_display_tiers(frame, _T)
    tiers = dict(zip(out["league"].to_list(), out["tier"].to_list(), strict=True))
    # >= at every cut; no quota - two leagues in one band share the tier.
    assert tiers == {"A": 1, "B": 2, "C": 2, "D": 4}
    assert out["tier"].dtype == pl.Int8


def test_one_season_blip_does_not_move_tier() -> None:
    frame = _strengths([("A", 2020, 15.6), ("A", 2021, 14.6), ("A", 2022, 15.6)])
    assert _tier_by_season(frame) == [1, 1, 1]


def test_two_consecutive_seasons_across_the_cut_move_the_tier() -> None:
    frame = _strengths([("A", 2020, 15.6), ("A", 2021, 14.6), ("A", 2022, 14.6)])
    assert _tier_by_season(frame) == [1, 1, 2]


def test_oscillation_across_a_cut_never_moves_the_tier() -> None:
    frame = _strengths([("A", 2020, 15.6), ("A", 2021, 14.6), ("A", 2022, 15.6), ("A", 2023, 14.6)])
    assert _tier_by_season(frame) == [1, 1, 1, 1]


def test_first_observed_season_takes_the_provisional_tier() -> None:
    frame = _strengths([("A", 2020, 13.6)])
    assert _tier_by_season(frame) == [3]


def test_null_strength_breaks_the_chain_and_restarts_fresh() -> None:
    frame = _strengths([("A", 2020, 15.6), ("A", 2021, None), ("A", 2022, 14.6)])
    # The null season has no tier; 2022 starts a new chain at its provisional
    # tier instead of inheriting the pre-gap assignment.
    assert _tier_by_season(frame) == [1, None, 2]


def test_missing_season_gap_restarts_the_chain() -> None:
    frame = _strengths([("A", 2018, 15.6), ("A", 2020, 14.6)])
    assert _tier_by_season(frame) == [1, 2]


def test_hysteresis_chains_are_per_league() -> None:
    frame = _strengths([("A", 2020, 15.6), ("A", 2021, 14.6), ("B", 2021, 14.6)])
    out = assign_display_tiers(frame, _T)
    by_key = {(row["league"], row["season"]): row["tier"] for row in out.iter_rows(named=True)}
    # A holds tier 1 through its blip; B's first season is provisional tier 2.
    assert by_key == {("A", 2020): 1, ("A", 2021): 1, ("B", 2021): 2}


def test_null_league_club_seasons_are_excluded_from_aggregation() -> None:
    rows = [
        {"club_id": 1, "league": "AA1", "squad_value_eur": 4_000_000},
        {"club_id": 2, "league": "AA1", "squad_value_eur": 2_000_000},
        {"club_id": 3, "league": None, "league_source": "none", "squad_value_eur": 90_000_000},
    ]
    out = league_seasons(_club_seasons(rows), _NO_LABELS, min_clubs=1)
    # No phantom null-league league-season row, and the unassigned club's
    # value never leaks into a median.
    assert out["league"].to_list() == ["AA1"]
    assert out["n_clubs"].to_list() == [2]
    assert out["median_squad_value_eur"].to_list() == [3_000_000]


def test_league_seasons_tiers_flow_from_thresholds_not_ranks() -> None:
    # 8M -> ln 15.9 (tier 1), 5M -> 15.4 (tier 2), 2M -> 14.5 (tier 2, boundary),
    # 1M -> 13.8 (tier 3). Equal medians share a tier - there is no quota and
    # no rank tie-break in tier assignment.
    rows = [
        {"club_id": 1, "league": "AA1", "squad_value_eur": 8_000_000},
        {"club_id": 2, "league": "BB1", "squad_value_eur": 5_000_000},
        {"club_id": 3, "league": "CC1", "squad_value_eur": 5_000_000},
        {"club_id": 4, "league": "DD1", "squad_value_eur": 2_000_000},
        {"club_id": 5, "league": "EE1", "squad_value_eur": 1_000_000},
    ]
    out = league_seasons(_club_seasons(rows), _NO_LABELS, min_clubs=1, tier_thresholds=_T)
    tiers = dict(zip(out["league"].to_list(), out["tier"].to_list(), strict=True))
    assert tiers == {"AA1": 1, "BB1": 2, "CC1": 2, "DD1": 2, "EE1": 3}


def test_strength_is_natural_log_of_median_null_when_not_positive() -> None:
    rows = [
        {"club_id": 1, "league": "AA1", "squad_value_eur": 1_000_000},
        {"club_id": 2, "league": "AA1", "squad_value_eur": 3_000_000},
        {"club_id": 3, "league": "ZZ1", "squad_value_eur": 0},
    ]
    out = league_seasons(_club_seasons(rows), _NO_LABELS, min_clubs=1)
    aa = out.filter(pl.col("league") == "AA1")
    assert aa["n_clubs"].item() == 2
    assert aa["median_squad_value_eur"].item() == 2_000_000
    assert aa["median_squad_value_eur"].dtype == pl.Int64
    assert aa["strength"].item() == pytest.approx(math.log(2_000_000))
    zz = out.filter(pl.col("league") == "ZZ1")
    assert zz["strength"].item() is None


def test_below_floor_league_season_gets_null_stats_and_flag() -> None:
    rows = [{"club_id": i, "league": "AA1", "squad_value_eur": 2_000_000} for i in range(1, 8)] + [
        {"club_id": 10 + i, "league": "BB1", "squad_value_eur": 1_000_000} for i in range(1, 9)
    ]
    out = league_seasons(_club_seasons(rows), _NO_LABELS, tier_thresholds=_T)  # default floor (8)
    aa = out.filter(pl.col("league") == "AA1")  # 7 members: below the floor
    assert aa["stats_valid"].item() is False
    assert aa["strength"].item() is None
    assert aa["tier"].item() is None
    assert aa["median_squad_value_eur"].item() == 2_000_000  # raw median still reported
    bb = out.filter(pl.col("league") == "BB1")  # 8 members: at the floor, valid
    assert bb["stats_valid"].item() is True
    assert bb["tier"].item() == 3  # ln(1M) ~ 13.8 under the test thresholds


def test_median_elo_ignores_nulls_and_coverage_counts_mapped_clubs() -> None:
    rows: list[dict[str, Any]] = [
        {"club_id": 1, "elo": 1500.0, "elo_mapped": True},
        {"club_id": 2, "elo": 1700.0, "elo_mapped": True},
        {"club_id": 3, "elo": None},
        {"club_id": 4, "elo": None},
    ]
    out = league_seasons(_club_seasons(rows, with_elo=True), _NO_LABELS, min_clubs=1)
    assert out.height == 1
    assert out["n_clubs"].item() == 4
    assert out["median_elo"].item() == pytest.approx(1600.0)
    assert out["elo_club_coverage"].item() == pytest.approx(0.5)


def test_missing_elo_columns_yield_null_median_and_zero_coverage() -> None:
    out = league_seasons(_club_seasons([{"club_id": 1}, {"club_id": 2}]), _NO_LABELS, min_clubs=1)
    assert out.columns == [
        "league",
        "season",
        "n_clubs",
        "median_squad_value_eur",
        "strength",
        "tier",
        "stats_valid",
        "median_elo",
        "elo_club_coverage",
        "league_name",
        "country",
    ]
    assert out["median_elo"].item() is None
    assert out["median_elo"].dtype == pl.Float64
    assert out["elo_club_coverage"].item() == 0.0


def test_league_name_and_country_come_from_competitions() -> None:
    competitions = make_competitions(
        [{"competition_id": "AA1", "name": "premier-league", "country_name": "England"}]
    )
    out = league_seasons(_club_seasons([{"club_id": 1}]), competitions, min_clubs=1)
    assert out["league_name"].to_list() == ["premier-league"]
    assert out["country"].to_list() == ["England"]


def test_league_missing_from_competitions_keeps_null_labels() -> None:
    competitions = make_competitions(
        [{"competition_id": "ZZ9", "name": "other", "country_name": "Nowhere"}]
    )
    out = league_seasons(_club_seasons([{"club_id": 1}]), competitions, min_clubs=1)
    assert out["league_name"].to_list() == [None]
    assert out["country"].to_list() == [None]
