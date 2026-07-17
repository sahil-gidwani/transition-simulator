"""profile_stats.parquet access."""

from __future__ import annotations

from typing import Any

import polars as pl


class ProfileRepo:
    def __init__(self, profile_stats: pl.DataFrame) -> None:
        self._stats = profile_stats

    def latest_row(self, player_id: int) -> dict[str, Any] | None:
        """The player's most recent season row.

        A mid-season mover can have two rows in the same season; the tie-break
        is deterministic: most minutes, then most games, then league code.
        """
        rows = self._stats.filter(pl.col("player_id") == player_id)
        if rows.is_empty():
            return None
        return rows.sort(
            ["season", "minutes", "games_played", "league"],
            descending=[True, True, True, False],
        ).row(0, named=True)

    def latest_minutes_share(self, player_id: int) -> float | None:
        row = self.latest_row(player_id)
        if row is None or row["minutes_share"] is None:
            return None
        return float(row["minutes_share"])
