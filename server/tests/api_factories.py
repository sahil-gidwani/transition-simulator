"""Synthetic PROCESSED-artifact builders for API tests (never real data).

Mirrors of the pipeline output schemas with exact dtypes, plus a store and
client factory. Distinct from factories.py, which builds RAW-table frames
for pipeline tests.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import polars as pl
from fastapi.testclient import TestClient

from app.core.clock import FixedClock
from app.main import create_app
from app.repositories.meta import BuildInfo
from app.repositories.players import PlayersRepo
from app.repositories.profiles import ProfileRepo
from app.repositories.seasons import SeasonsRepo
from app.repositories.store import DataStore
from app.repositories.transitions import TransitionsRepo

TODAY = date(2026, 7, 17)

_PLAYERS_DEFAULTS: dict[str, Any] = {
    "player_id": 1,
    "name": "Player One",
    "position_group": "ATT",
    "sub_position": "Centre-Forward",
    "date_of_birth": date(1998, 6, 15),
    "foot": "right",
    "height_cm": 180,
    "current_club_id": 10,
    "current_club_name": "Alpha FC",
    "current_league": "AA1",
    "market_value_eur": 10_000_000,
    "market_value_asof": date(2026, 6, 1),
    "last_season": 2025,
}
_PLAYERS_SCHEMA: dict[str, pl.DataType | type[pl.DataType]] = {
    "player_id": pl.Int32,
    "name": pl.String,
    "position_group": pl.String,
    "sub_position": pl.String,
    "date_of_birth": pl.Date,
    "foot": pl.String,
    "height_cm": pl.Int16,
    "current_club_id": pl.Int32,
    "current_club_name": pl.String,
    "current_league": pl.String,
    "market_value_eur": pl.Int64,
    "market_value_asof": pl.Date,
    "last_season": pl.Int16,
}

_PLAYER_VALUES_DEFAULTS: dict[str, Any] = {
    "player_id": 1,
    "date": date(2026, 6, 1),
    "market_value_eur": 10_000_000,
}
_PLAYER_VALUES_SCHEMA: dict[str, pl.DataType | type[pl.DataType]] = {
    "player_id": pl.Int32,
    "date": pl.Date,
    "market_value_eur": pl.Int64,
}

_TRANSITIONS_DEFAULTS: dict[str, Any] = {
    "player_id": 100,
    "player_name": "Comp Player",
    "transfer_date": date(2023, 7, 1),
    "season": 2023,
    "age_at_transfer": 25.0,
    "position_group": "ATT",
    "sub_position": "Centre-Forward",
    "from_club_id": 11,
    "to_club_id": 21,
    "from_club_name": "Origin FC",
    "to_club_name": "Dest FC",
    "from_league": "AA1",
    "to_league": "BB1",
    "from_tier": 1,
    "to_tier": 1,
    "from_tercile": 1,
    "to_tercile": 2,
    "from_elo": 1500.0,
    "from_elo_pct": 0.5,
    "to_elo": 1600.0,
    "to_elo_pct": 0.7,
    "v_before": 10_000_000,
    "v_before_date": date(2023, 6, 1),
    "v_after": 12_000_000,
    "v_after_date": date(2024, 7, 1),
    "multiplier": 1.2,
    "delta_pct": 0.2,
    "days_to_after": 366,
    "transfer_fee_eur": 15_000_000,
    "minutes_share_pre": 0.8,
    "suspected_loan": False,
}
_TRANSITIONS_SCHEMA: dict[str, pl.DataType | type[pl.DataType]] = {
    "player_id": pl.Int32,
    "player_name": pl.String,
    "transfer_date": pl.Date,
    "season": pl.Int16,
    "age_at_transfer": pl.Float32,
    "position_group": pl.String,
    "sub_position": pl.String,
    "from_club_id": pl.Int32,
    "to_club_id": pl.Int32,
    "from_club_name": pl.String,
    "to_club_name": pl.String,
    "from_league": pl.String,
    "to_league": pl.String,
    "from_tier": pl.Int8,
    "to_tier": pl.Int8,
    "from_tercile": pl.Int8,
    "to_tercile": pl.Int8,
    "from_elo": pl.Float32,
    "from_elo_pct": pl.Float32,
    "to_elo": pl.Float32,
    "to_elo_pct": pl.Float32,
    "v_before": pl.Int64,
    "v_before_date": pl.Date,
    "v_after": pl.Int64,
    "v_after_date": pl.Date,
    "multiplier": pl.Float64,
    "delta_pct": pl.Float64,
    "days_to_after": pl.Int16,
    "transfer_fee_eur": pl.Int64,
    "minutes_share_pre": pl.Float32,
    "suspected_loan": pl.Boolean,
}

_LEAGUE_SEASONS_DEFAULTS: dict[str, Any] = {
    "league": "AA1",
    "season": 2025,
    "n_clubs": 18,
    "median_squad_value_eur": 100_000_000,
    "strength": 18.4,
    "tier": 1,
    "median_elo": 1700.0,
    "elo_club_coverage": 1.0,
    "league_name": "league-alpha",
    "country": "Alphaland",
}
_LEAGUE_SEASONS_SCHEMA: dict[str, pl.DataType | type[pl.DataType]] = {
    "league": pl.String,
    "season": pl.Int16,
    "n_clubs": pl.Int16,
    "median_squad_value_eur": pl.Int64,
    "strength": pl.Float64,
    "tier": pl.Int8,
    "median_elo": pl.Float32,
    "elo_club_coverage": pl.Float32,
    "league_name": pl.String,
    "country": pl.String,
}

_CLUB_SEASONS_DEFAULTS: dict[str, Any] = {
    "club_id": 10,
    "season": 2025,
    "club_name": "Alpha FC",
    "league": "AA1",
    "league_source": "games",
    "squad_value_eur": 200_000_000,
    "n_valued_players": 25,
    "tercile": 1,
    "elo": 1800.0,
    "elo_pct": 0.9,
    "elo_date": date(2025, 7, 1),
    "elo_mapped": True,
}
_CLUB_SEASONS_SCHEMA: dict[str, pl.DataType | type[pl.DataType]] = {
    "club_id": pl.Int32,
    "season": pl.Int16,
    "club_name": pl.String,
    "league": pl.String,
    "league_source": pl.String,
    "squad_value_eur": pl.Int64,
    "n_valued_players": pl.Int16,
    "tercile": pl.Int8,
    "elo": pl.Float32,
    "elo_pct": pl.Float32,
    "elo_date": pl.Date,
    "elo_mapped": pl.Boolean,
}

_PROFILE_DEFAULTS: dict[str, Any] = {
    "player_id": 1,
    "season": 2025,
    "league": "AA1",
    "position_group": "ATT",
    "games_played": 30,
    "minutes": 2700,
    "goals": 12,
    "assists": 5,
    "cards": 3,
    "minutes_share": 0.79,
    "goals_p90": 0.4,
    "assists_p90": 0.17,
    "ga_p90": 0.57,
    "cards_p90": 0.1,
    "conceded_p90": None,
    "clean_sheet_rate": None,
    "pct_goals_p90": 0.8,
    "pct_assists_p90": 0.6,
    "pct_ga_p90": 0.75,
    "pct_cards_p90": 0.5,
    "pct_conceded_p90": None,
    "pct_clean_sheet_rate": None,
    "peer_n": 40,
}
_PROFILE_SCHEMA: dict[str, pl.DataType | type[pl.DataType]] = {
    "player_id": pl.Int32,
    "season": pl.Int16,
    "league": pl.String,
    "position_group": pl.String,
    "games_played": pl.Int16,
    "minutes": pl.Int32,
    "goals": pl.Int16,
    "assists": pl.Int16,
    "cards": pl.Int16,
    "minutes_share": pl.Float32,
    "goals_p90": pl.Float32,
    "assists_p90": pl.Float32,
    "ga_p90": pl.Float32,
    "cards_p90": pl.Float32,
    "conceded_p90": pl.Float32,
    "clean_sheet_rate": pl.Float32,
    "pct_goals_p90": pl.Float32,
    "pct_assists_p90": pl.Float32,
    "pct_ga_p90": pl.Float32,
    "pct_cards_p90": pl.Float32,
    "pct_conceded_p90": pl.Float32,
    "pct_clean_sheet_rate": pl.Float32,
    "peer_n": pl.Int16,
}


def _build(
    defaults: dict[str, Any],
    schema: dict[str, pl.DataType | type[pl.DataType]],
    rows: list[dict[str, Any]],
) -> pl.DataFrame:
    return pl.DataFrame([{**defaults, **row} for row in rows], schema=schema)


def make_players_processed(rows: list[dict[str, Any]]) -> pl.DataFrame:
    return _build(_PLAYERS_DEFAULTS, _PLAYERS_SCHEMA, rows)


def make_player_values(rows: list[dict[str, Any]]) -> pl.DataFrame:
    return _build(_PLAYER_VALUES_DEFAULTS, _PLAYER_VALUES_SCHEMA, rows)


def make_transitions(rows: list[dict[str, Any]]) -> pl.DataFrame:
    return _build(_TRANSITIONS_DEFAULTS, _TRANSITIONS_SCHEMA, rows)


def make_league_seasons(rows: list[dict[str, Any]]) -> pl.DataFrame:
    return _build(_LEAGUE_SEASONS_DEFAULTS, _LEAGUE_SEASONS_SCHEMA, rows)


def make_club_seasons(rows: list[dict[str, Any]]) -> pl.DataFrame:
    return _build(_CLUB_SEASONS_DEFAULTS, _CLUB_SEASONS_SCHEMA, rows)


def make_profile_stats(rows: list[dict[str, Any]]) -> pl.DataFrame:
    return _build(_PROFILE_DEFAULTS, _PROFILE_SCHEMA, rows)


def make_build_info(**overrides: Any) -> BuildInfo:
    payload: dict[str, Any] = {
        "repo": "example/mirror",
        "revision": "abc123",
        "built_at": "2026-07-17T12:00:00+00:00",
        "max_valuation_date": date(2026, 6, 12),
        "censor_horizon": date(2025, 12, 14),
        "season_min": 2012,
        "profile_min_minutes": 450,
        "comps_universe_size": 19_407,
    }
    payload.update(overrides)
    return BuildInfo(**payload)


def make_meta_payload() -> dict[str, Any]:
    """A minimal meta.json payload matching what read_build_info consumes."""
    return {
        "source": {"source": "huggingface", "repo": "example/mirror", "revision": "abc123"},
        "built_at": "2026-07-17T12:00:00+00:00",
        "valuation_freshness": {
            "max_valuation_date": "2026-06-12",
            "censor_horizon": "2025-12-14",
        },
        "constants": {"season_min": 2012, "profile_min_minutes": 450},
        "funnel": {"transitions_non_loan_2012_plus": 19_407},
    }


def make_store(
    players: pl.DataFrame | None = None,
    player_values: pl.DataFrame | None = None,
    transitions: pl.DataFrame | None = None,
    league_seasons: pl.DataFrame | None = None,
    club_seasons: pl.DataFrame | None = None,
    profile_stats: pl.DataFrame | None = None,
    build_info: BuildInfo | None = None,
) -> DataStore:
    return DataStore(
        players=PlayersRepo(
            players if players is not None else make_players_processed([]),
            player_values if player_values is not None else make_player_values([]),
        ),
        transitions=TransitionsRepo(
            transitions if transitions is not None else make_transitions([])
        ),
        seasons=SeasonsRepo(
            league_seasons if league_seasons is not None else make_league_seasons([]),
            club_seasons if club_seasons is not None else make_club_seasons([]),
        ),
        profiles=ProfileRepo(
            profile_stats if profile_stats is not None else make_profile_stats([])
        ),
        build_info=build_info if build_info is not None else make_build_info(),
    )


def make_client(store: DataStore, today: date = TODAY) -> TestClient:
    return TestClient(create_app(store=store, clock=FixedClock(today)))
