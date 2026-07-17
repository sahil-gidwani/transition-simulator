import math
from typing import Any

import polars as pl
import pytest
from factories import make_competitions

from pipeline.transforms.leagues import league_seasons

_NO_LABELS = make_competitions([])

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


def test_tiers_split_eight_leagues_two_per_tier() -> None:
    rows = [
        {"club_id": i, "league": f"L{i}", "squad_value_eur": (9 - i) * 1_000_000}
        for i in range(1, 9)
    ]
    out = league_seasons(_club_seasons(rows), _NO_LABELS)
    # Sorted by league code, and league Li has the i-th highest median.
    assert out["league"].to_list() == [f"L{i}" for i in range(1, 9)]
    assert out["tier"].to_list() == [1, 1, 2, 2, 3, 3, 4, 4]
    assert out["tier"].dtype == pl.Int8


def test_tiers_split_five_leagues_two_one_one_one() -> None:
    # Documented unevenness: with 5 leagues the top tier holds two of them.
    rows = [
        {"club_id": i, "league": f"L{i}", "squad_value_eur": (6 - i) * 1_000_000}
        for i in range(1, 6)
    ]
    out = league_seasons(_club_seasons(rows), _NO_LABELS)
    assert out["tier"].to_list() == [1, 1, 2, 3, 4]


def test_median_tie_broken_by_league_code_ascending() -> None:
    rows = [
        {"club_id": 1, "league": "BB1", "squad_value_eur": 5_000_000},
        {"club_id": 2, "league": "AA1", "squad_value_eur": 5_000_000},
        {"club_id": 3, "league": "CC1", "squad_value_eur": 2_000_000},
        {"club_id": 4, "league": "DD1", "squad_value_eur": 1_000_000},
    ]
    out = league_seasons(_club_seasons(rows), _NO_LABELS)
    tiers = dict(zip(out["league"].to_list(), out["tier"].to_list(), strict=True))
    assert tiers == {"AA1": 1, "BB1": 2, "CC1": 3, "DD1": 4}


def test_strength_is_natural_log_of_median_null_when_not_positive() -> None:
    rows = [
        {"club_id": 1, "league": "AA1", "squad_value_eur": 1_000_000},
        {"club_id": 2, "league": "AA1", "squad_value_eur": 3_000_000},
        {"club_id": 3, "league": "ZZ1", "squad_value_eur": 0},
    ]
    out = league_seasons(_club_seasons(rows), _NO_LABELS)
    aa = out.filter(pl.col("league") == "AA1")
    assert aa["n_clubs"].item() == 2
    assert aa["median_squad_value_eur"].item() == 2_000_000
    assert aa["median_squad_value_eur"].dtype == pl.Int64
    assert aa["strength"].item() == pytest.approx(math.log(2_000_000))
    zz = out.filter(pl.col("league") == "ZZ1")
    assert zz["strength"].item() is None


def test_median_elo_ignores_nulls_and_coverage_counts_mapped_clubs() -> None:
    rows: list[dict[str, Any]] = [
        {"club_id": 1, "elo": 1500.0, "elo_mapped": True},
        {"club_id": 2, "elo": 1700.0, "elo_mapped": True},
        {"club_id": 3, "elo": None},
        {"club_id": 4, "elo": None},
    ]
    out = league_seasons(_club_seasons(rows, with_elo=True), _NO_LABELS)
    assert out.height == 1
    assert out["n_clubs"].item() == 4
    assert out["median_elo"].item() == pytest.approx(1600.0)
    assert out["elo_club_coverage"].item() == pytest.approx(0.5)


def test_missing_elo_columns_yield_null_median_and_zero_coverage() -> None:
    out = league_seasons(_club_seasons([{"club_id": 1}, {"club_id": 2}]), _NO_LABELS)
    assert out.columns == [
        "league",
        "season",
        "n_clubs",
        "median_squad_value_eur",
        "strength",
        "tier",
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
    out = league_seasons(_club_seasons([{"club_id": 1}]), competitions)
    assert out["league_name"].to_list() == ["premier-league"]
    assert out["country"].to_list() == ["England"]


def test_league_missing_from_competitions_keeps_null_labels() -> None:
    competitions = make_competitions(
        [{"competition_id": "ZZ9", "name": "other", "country_name": "Nowhere"}]
    )
    out = league_seasons(_club_seasons([{"club_id": 1}]), competitions)
    assert out["league_name"].to_list() == [None]
    assert out["country"].to_list() == [None]
