"""Synthetic raw-table builders for pipeline tests.

Each builder takes a list of per-row overrides and fills the remaining columns
with neutral defaults, using the dtypes the raw CSV scans produce. Tests never
touch real data.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import polars as pl

_TRANSFERS_DEFAULTS: dict[str, Any] = {
    "player_id": 1,
    "transfer_date": date(2020, 7, 1),
    "transfer_season": "20/21",
    "from_club_id": 10,
    "to_club_id": 20,
    "from_club_name": "From FC",
    "to_club_name": "To FC",
    "transfer_fee": 1_000_000.0,
    "market_value_in_eur": 5_000_000.0,
    "player_name": "Player One",
}
_TRANSFERS_SCHEMA: dict[str, pl.DataType | type[pl.DataType]] = {
    "player_id": pl.Int64,
    "transfer_date": pl.Date,
    "transfer_season": pl.String,
    "from_club_id": pl.Int64,
    "to_club_id": pl.Int64,
    "from_club_name": pl.String,
    "to_club_name": pl.String,
    "transfer_fee": pl.Float64,
    "market_value_in_eur": pl.Float64,
    "player_name": pl.String,
}

_VALUATIONS_DEFAULTS: dict[str, Any] = {
    "player_id": 1,
    "date": date(2020, 1, 1),
    "market_value_in_eur": 5_000_000,
    "current_club_id": 10,
    "player_club_domestic_competition_id": "AA1",
}
_VALUATIONS_SCHEMA: dict[str, pl.DataType | type[pl.DataType]] = {
    "player_id": pl.Int64,
    "date": pl.Date,
    "market_value_in_eur": pl.Int64,
    "current_club_id": pl.Int64,
    "player_club_domestic_competition_id": pl.String,
}

_PLAYERS_DEFAULTS: dict[str, Any] = {
    "player_id": 1,
    "name": "Player One",
    "last_season": 2024,
    "current_club_id": 10,
    "date_of_birth": date(1995, 6, 15),
    "sub_position": "Centre-Forward",
    "position": "Attack",
    "foot": "right",
    "height_in_cm": 180,
    "current_club_domestic_competition_id": "AA1",
    "current_club_name": "From FC",
    "market_value_in_eur": 5_000_000,
}
_PLAYERS_SCHEMA: dict[str, pl.DataType | type[pl.DataType]] = {
    "player_id": pl.Int64,
    "name": pl.String,
    "last_season": pl.Int64,
    "current_club_id": pl.Int64,
    "date_of_birth": pl.Date,
    "sub_position": pl.String,
    "position": pl.String,
    "foot": pl.String,
    "height_in_cm": pl.Int64,
    "current_club_domestic_competition_id": pl.String,
    "current_club_name": pl.String,
    "market_value_in_eur": pl.Int64,
}

_CLUBS_DEFAULTS: dict[str, Any] = {
    "club_id": 10,
    "club_code": "from-fc",
    "name": "From FC",
    "domestic_competition_id": "AA1",
    "last_season": 2024,
}
_CLUBS_SCHEMA: dict[str, pl.DataType | type[pl.DataType]] = {
    "club_id": pl.Int64,
    "club_code": pl.String,
    "name": pl.String,
    "domestic_competition_id": pl.String,
    "last_season": pl.Int64,
}

_COMPETITIONS_DEFAULTS: dict[str, Any] = {
    "competition_id": "AA1",
    "competition_code": "league-a",
    "name": "league-a",
    "sub_type": "first_tier",
    "type": "domestic_league",
    "country_name": "Aland",
    "domestic_league_code": "AA1",
    "confederation": "europa",
}
_COMPETITIONS_SCHEMA: dict[str, pl.DataType | type[pl.DataType]] = {
    "competition_id": pl.String,
    "competition_code": pl.String,
    "name": pl.String,
    "sub_type": pl.String,
    "type": pl.String,
    "country_name": pl.String,
    "domestic_league_code": pl.String,
    "confederation": pl.String,
}

_GAMES_DEFAULTS: dict[str, Any] = {
    "game_id": 100,
    "competition_id": "AA1",
    "season": 2020,
    "date": date(2020, 8, 1),
    "home_club_id": 10,
    "away_club_id": 20,
    "home_club_goals": 1,
    "away_club_goals": 1,
    "competition_type": "domestic_league",
}
_GAMES_SCHEMA: dict[str, pl.DataType | type[pl.DataType]] = {
    "game_id": pl.Int64,
    "competition_id": pl.String,
    "season": pl.Int64,
    "date": pl.Date,
    "home_club_id": pl.Int64,
    "away_club_id": pl.Int64,
    "home_club_goals": pl.Int64,
    "away_club_goals": pl.Int64,
    "competition_type": pl.String,
}

_APPEARANCES_DEFAULTS: dict[str, Any] = {
    "appearance_id": "100_1",
    "game_id": 100,
    "player_id": 1,
    "player_club_id": 10,
    "date": date(2020, 8, 1),
    "competition_id": "AA1",
    "yellow_cards": 0,
    "red_cards": 0,
    "goals": 0,
    "assists": 0,
    "minutes_played": 90,
}
_APPEARANCES_SCHEMA: dict[str, pl.DataType | type[pl.DataType]] = {
    "appearance_id": pl.String,
    "game_id": pl.Int64,
    "player_id": pl.Int64,
    "player_club_id": pl.Int64,
    "date": pl.Date,
    "competition_id": pl.String,
    "yellow_cards": pl.Int64,
    "red_cards": pl.Int64,
    "goals": pl.Int64,
    "assists": pl.Int64,
    "minutes_played": pl.Int64,
}

_CLUB_GAMES_DEFAULTS: dict[str, Any] = {
    "game_id": 100,
    "club_id": 10,
    "own_goals": 1,
    "opponent_id": 20,
    "opponent_goals": 1,
    "hosting": "Home",
    "is_win": 0,
}
_CLUB_GAMES_SCHEMA: dict[str, pl.DataType | type[pl.DataType]] = {
    "game_id": pl.Int64,
    "club_id": pl.Int64,
    "own_goals": pl.Int64,
    "opponent_id": pl.Int64,
    "opponent_goals": pl.Int64,
    "hosting": pl.String,
    "is_win": pl.Int64,
}


def _build(
    defaults: dict[str, Any],
    schema: dict[str, pl.DataType | type[pl.DataType]],
    rows: list[dict[str, Any]],
) -> pl.DataFrame:
    data = [{**defaults, **row} for row in rows]
    return pl.DataFrame(data, schema=schema)


def make_transfers(rows: list[dict[str, Any]]) -> pl.DataFrame:
    return _build(_TRANSFERS_DEFAULTS, _TRANSFERS_SCHEMA, rows)


def make_valuations(rows: list[dict[str, Any]]) -> pl.DataFrame:
    return _build(_VALUATIONS_DEFAULTS, _VALUATIONS_SCHEMA, rows)


def make_players(rows: list[dict[str, Any]]) -> pl.DataFrame:
    return _build(_PLAYERS_DEFAULTS, _PLAYERS_SCHEMA, rows)


def make_clubs(rows: list[dict[str, Any]]) -> pl.DataFrame:
    return _build(_CLUBS_DEFAULTS, _CLUBS_SCHEMA, rows)


def make_competitions(rows: list[dict[str, Any]]) -> pl.DataFrame:
    return _build(_COMPETITIONS_DEFAULTS, _COMPETITIONS_SCHEMA, rows)


def make_games(rows: list[dict[str, Any]]) -> pl.DataFrame:
    return _build(_GAMES_DEFAULTS, _GAMES_SCHEMA, rows)


def make_appearances(rows: list[dict[str, Any]]) -> pl.DataFrame:
    return _build(_APPEARANCES_DEFAULTS, _APPEARANCES_SCHEMA, rows)


def make_club_games(rows: list[dict[str, Any]]) -> pl.DataFrame:
    return _build(_CLUB_GAMES_DEFAULTS, _CLUB_GAMES_SCHEMA, rows)
