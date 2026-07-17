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
