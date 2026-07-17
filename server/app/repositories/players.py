"""players.parquet + player_values.parquet access."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import polars as pl

from app.core.text import normalize_search_text


@dataclass(frozen=True)
class PlayerRecord:
    player_id: int
    name: str
    position_group: str
    sub_position: str | None
    date_of_birth: date | None
    foot: str | None
    height_cm: int | None
    current_club_id: int
    current_club_name: str
    current_league: str
    market_value_eur: int | None
    market_value_asof: date | None
    last_season: int


@dataclass(frozen=True)
class ValuePoint:
    date: date
    value_eur: int


def _record(row: dict[str, Any]) -> PlayerRecord:
    return PlayerRecord(
        player_id=row["player_id"],
        name=row["name"],
        position_group=row["position_group"],
        sub_position=row["sub_position"],
        date_of_birth=row["date_of_birth"],
        foot=row["foot"],
        height_cm=row["height_cm"],
        current_club_id=row["current_club_id"],
        current_club_name=row["current_club_name"],
        current_league=row["current_league"],
        market_value_eur=row["market_value_eur"],
        market_value_asof=row["market_value_asof"],
        last_season=row["last_season"],
    )


class PlayersRepo:
    def __init__(self, players: pl.DataFrame, values: pl.DataFrame) -> None:
        self._players = players.with_columns(
            pl.col("name")
            .map_elements(normalize_search_text, return_dtype=pl.String)
            .alias("name_norm")
        )
        self._values = values

    def get(self, player_id: int) -> PlayerRecord | None:
        rows = self._players.filter(pl.col("player_id") == player_id)
        if rows.is_empty():
            return None
        return _record(rows.row(0, named=True))

    def search(self, query_norm: str, limit: int) -> list[PlayerRecord]:
        """Ranked matches on the normalized name: full prefix, then a token
        prefix, then any substring; ties by market value desc (nulls last),
        then name."""
        if not query_norm:
            return []
        matches = (
            self._players.filter(pl.col("name_norm").str.contains(query_norm, literal=True))
            .with_columns(
                rank=pl.when(pl.col("name_norm").str.starts_with(query_norm))
                .then(0)
                .when(pl.col("name_norm").str.contains(f" {query_norm}", literal=True))
                .then(1)
                .otherwise(2)
            )
            .sort(
                ["rank", "market_value_eur", "name"],
                descending=[False, True, False],
                nulls_last=True,
            )
            .head(limit)
        )
        return [_record(row) for row in matches.iter_rows(named=True)]

    def value_history(self, player_id: int) -> list[ValuePoint]:
        rows = self._values.filter(pl.col("player_id") == player_id).sort("date")
        return [
            ValuePoint(date=d, value_eur=v)
            for d, v in rows.select("date", "market_value_eur").iter_rows()
        ]
