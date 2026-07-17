from datetime import date

from factories import make_competitions, make_players, make_valuations

from pipeline.transforms.players import PLAYERS_SCHEMA, assemble_players


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
