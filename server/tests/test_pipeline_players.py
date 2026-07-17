from datetime import date

import polars as pl
from factories import make_competitions, make_players, make_valuations

from pipeline.transforms.players import (
    PLAYER_VALUES_SCHEMA,
    PLAYERS_SCHEMA,
    assemble_players,
    player_value_history,
)


def test_only_players_in_covered_leagues_kept() -> None:
    players = make_players(
        [
            {"player_id": 1, "current_club_domestic_competition_id": "AA1"},
            {"player_id": 2, "current_club_domestic_competition_id": "XX9"},
        ]
    )
    competitions = make_competitions([{"competition_id": "AA1", "type": "domestic_league"}])
    out = assemble_players(players, make_valuations([]), competitions)
    assert out["player_id"].to_list() == [1]


def test_value_and_asof_come_from_latest_valuation() -> None:
    players = make_players([{"player_id": 1, "market_value_in_eur": 999}])
    valuations = make_valuations(
        [
            {"player_id": 1, "date": date(2025, 1, 1), "market_value_in_eur": 3_000_000},
            {"player_id": 1, "date": date(2026, 2, 1), "market_value_in_eur": 4_000_000},
        ]
    )
    competitions = make_competitions([{"competition_id": "AA1", "type": "domestic_league"}])
    out = assemble_players(players, valuations, competitions)
    assert out["market_value_eur"].to_list() == [4_000_000]
    assert out["market_value_asof"].to_list() == [date(2026, 2, 1)]


def test_no_valuation_history_means_null_value_and_null_date() -> None:
    # Never a value without an as-of date: the players.csv snapshot value is
    # undated, so it is not used as a fallback.
    players = make_players([{"player_id": 1, "market_value_in_eur": 999}])
    competitions = make_competitions([{"competition_id": "AA1", "type": "domestic_league"}])
    out = assemble_players(players, make_valuations([]), competitions)
    assert out["market_value_eur"].to_list() == [None]
    assert out["market_value_asof"].to_list() == [None]


def test_zero_valuation_is_a_sentinel_not_a_price() -> None:
    # Upstream writes 0 for "no valuation"; the latest REAL price wins, and a
    # player with only zero rows carries null value + null date.
    players = make_players([{"player_id": 1}, {"player_id": 2}])
    valuations = make_valuations(
        [
            {"player_id": 1, "date": date(2025, 1, 1), "market_value_in_eur": 3_000_000},
            {"player_id": 1, "date": date(2026, 2, 1), "market_value_in_eur": 0},
            {"player_id": 2, "date": date(2026, 2, 1), "market_value_in_eur": 0},
        ]
    )
    competitions = make_competitions([{"competition_id": "AA1", "type": "domestic_league"}])
    out = assemble_players(players, valuations, competitions)
    assert out["market_value_eur"].to_list() == [3_000_000, None]
    assert out["market_value_asof"].to_list() == [date(2025, 1, 1), None]


def test_schema_and_sort_contract() -> None:
    players = make_players(
        [
            {"player_id": 5, "sub_position": None, "position": "Midfield"},
            {"player_id": 3, "sub_position": "Goalkeeper", "position": "Goalkeeper"},
        ]
    )
    competitions = make_competitions([{"competition_id": "AA1", "type": "domestic_league"}])
    out = assemble_players(players, make_valuations([]), competitions)
    assert dict(out.schema) == PLAYERS_SCHEMA
    assert out["player_id"].to_list() == [3, 5]
    assert out["position_group"].to_list() == ["GK", "MID"]


def _players_final(valuations: pl.DataFrame) -> pl.DataFrame:
    players = make_players(
        [
            {"player_id": 1, "current_club_domestic_competition_id": "AA1"},
            {"player_id": 2, "current_club_domestic_competition_id": "XX9"},
        ]
    )
    competitions = make_competitions([{"competition_id": "AA1", "type": "domestic_league"}])
    return assemble_players(players, valuations, competitions)


def test_value_history_keeps_only_in_scope_players() -> None:
    valuations = make_valuations(
        [
            {"player_id": 1, "date": date(2020, 1, 1), "market_value_in_eur": 1_000_000},
            {"player_id": 2, "date": date(2020, 1, 1), "market_value_in_eur": 2_000_000},
        ]
    )
    out = player_value_history(valuations, _players_final(valuations))
    assert out["player_id"].to_list() == [1]


def test_value_history_drops_rows_with_null_date_or_non_positive_value() -> None:
    valuations = make_valuations(
        [
            {"player_id": 1, "date": date(2020, 1, 1), "market_value_in_eur": 1_000_000},
            {"player_id": 1, "date": None, "market_value_in_eur": 2_000_000},
            {"player_id": 1, "date": date(2021, 1, 1), "market_value_in_eur": None},
            {"player_id": 1, "date": date(2022, 1, 1), "market_value_in_eur": 0},
        ]
    )
    out = player_value_history(valuations, _players_final(valuations))
    assert out["date"].to_list() == [date(2020, 1, 1)]


def test_value_history_schema_and_sort() -> None:
    valuations = make_valuations(
        [
            {"player_id": 1, "date": date(2021, 6, 1), "market_value_in_eur": 3_000_000},
            {"player_id": 1, "date": date(2019, 6, 1), "market_value_in_eur": 1_000_000},
            {"player_id": 1, "date": date(2020, 6, 1), "market_value_in_eur": 2_000_000},
        ]
    )
    out = player_value_history(valuations, _players_final(valuations))
    assert dict(out.schema) == PLAYER_VALUES_SCHEMA
    assert out["date"].to_list() == [date(2019, 6, 1), date(2020, 6, 1), date(2021, 6, 1)]
    assert out["market_value_eur"].to_list() == [1_000_000, 2_000_000, 3_000_000]
