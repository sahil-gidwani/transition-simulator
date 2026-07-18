"""transitions.parquet access: the comps universe."""

from __future__ import annotations

import polars as pl


class TransitionsRepo:
    def __init__(self, transitions: pl.DataFrame) -> None:
        # Suspected loans are excluded once, here: no comp query ever sees them.
        self._universe = transitions.filter(~pl.col("suspected_loan"))

    @property
    def comps_universe(self) -> pl.DataFrame:
        """Non-loan transitions - the only rows the comps engine may match."""
        return self._universe

    def player_transfers(self, player_id: int) -> pl.DataFrame:
        """The player's own qualifying (non-loan) moves, oldest first — the
        profile chart's annotations, not comps. Only qualifying transfers
        exist in the artifact, so out-of-scope moves simply don't annotate."""
        return (
            self._universe.filter(pl.col("player_id") == player_id)
            .sort("transfer_date")
            .select("transfer_date", "from_club_name", "to_club_name")
        )
