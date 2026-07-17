"""Per-query backtest records: the one frame every metric reads.

Pure builders only - the CLI owns all filesystem writes (mirroring the
build pipeline's io discipline). Quantile columns are null exactly when
the engine refused (insufficient precedent); baseline columns are null
only when the availability-filtered universe was too thin to quote.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import polars as pl

RECORDS_SCHEMA: dict[str, pl.DataType | type[pl.DataType]] = {
    "player_id": pl.Int32,
    "transfer_date": pl.Date,
    "season": pl.Int16,
    "v_before": pl.Int64,
    "v_after": pl.Int64,
    "actual_multiplier": pl.Float64,
    "q25": pl.Float64,
    "q50": pl.Float64,
    "q75": pl.Float64,
    "insufficient": pl.Boolean,
    "pool_size": pl.Int16,
    "relaxation_level": pl.Int8,
    "confidence": pl.String,
    "iqr_log": pl.Float64,
    "n_available": pl.Int32,
    "b1_q25": pl.Float64,
    "b1_q50": pl.Float64,
    "b1_q75": pl.Float64,
    "b2_q25": pl.Float64,
    "b2_q50": pl.Float64,
    "b2_q75": pl.Float64,
    "b2_fallback": pl.Boolean,
    "age_at_transfer": pl.Float32,
    "position_group": pl.String,
    "from_tier": pl.Int8,
    "to_tier": pl.Int8,
    "minutes_known": pl.Boolean,
}


@dataclass(frozen=True)
class PredictionRecord:
    """One held-out query: what the engine predicted vs what happened."""

    player_id: int
    transfer_date: date
    season: int
    v_before: int
    v_after: int
    actual_multiplier: float
    q25: float | None
    q50: float | None
    q75: float | None
    insufficient: bool
    pool_size: int
    relaxation_level: int
    confidence: str
    iqr_log: float | None
    n_available: int
    b1_q25: float | None
    b1_q50: float | None
    b1_q75: float | None
    b2_q25: float | None
    b2_q50: float | None
    b2_q75: float | None
    b2_fallback: bool
    age_at_transfer: float | None
    position_group: str
    from_tier: int | None
    to_tier: int
    minutes_known: bool


def records_frame(records: list[PredictionRecord]) -> pl.DataFrame:
    return pl.DataFrame(
        [{name: getattr(record, name) for name in RECORDS_SCHEMA} for record in records],
        schema=RECORDS_SCHEMA,
    )
