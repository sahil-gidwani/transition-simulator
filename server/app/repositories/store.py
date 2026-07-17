"""DataStore: every processed artifact, loaded once at startup and shared.

Repositories are the ONLY code that touches the parquet files; routes receive
the store through the get_store dependency and hand frames to services.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

import polars as pl
from fastapi import Request

from app.repositories.meta import BuildInfo, read_build_info
from app.repositories.players import PlayersRepo
from app.repositories.profiles import ProfileRepo
from app.repositories.seasons import SeasonsRepo
from app.repositories.transitions import TransitionsRepo


@dataclass(frozen=True)
class DataStore:
    players: PlayersRepo
    transitions: TransitionsRepo
    seasons: SeasonsRepo
    profiles: ProfileRepo
    build_info: BuildInfo


def _read(data_dir: Path, name: str) -> pl.DataFrame:
    path = data_dir / name
    if not path.exists():
        raise FileNotFoundError(
            f"processed artifact missing: {path} - run `uv run python -m pipeline.build`"
        )
    return pl.read_parquet(path)


def load_store(data_dir: Path) -> DataStore:
    return DataStore(
        players=PlayersRepo(
            _read(data_dir, "players.parquet"), _read(data_dir, "player_values.parquet")
        ),
        transitions=TransitionsRepo(_read(data_dir, "transitions.parquet")),
        seasons=SeasonsRepo(
            _read(data_dir, "league_seasons.parquet"), _read(data_dir, "club_seasons.parquet")
        ),
        profiles=ProfileRepo(_read(data_dir, "profile_stats.parquet")),
        build_info=read_build_info(data_dir / "meta.json"),
    )


def get_store(request: Request) -> DataStore:
    store = request.app.state.store
    if store is None:
        raise RuntimeError(
            "DataStore not initialized: the app started without its lifespan or an injected store"
        )
    return cast(DataStore, store)
