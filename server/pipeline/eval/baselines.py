"""Naive precedent-free baselines under the same availability rule.

Computed per query on the ALREADY availability-filtered universe frame:
the runner hands the exact frame it gives find_comps, so a second
(possibly divergent) leakage rule cannot exist. Quantiles are plain
empirical (linear interpolation) - these are independent estimators, not
weighted pools. B0 (multiplier = 1) needs no computation and is scored
directly in the metrics stage.
"""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

from pipeline.eval.metrics import AGE_BANDS, age_band_label

MIN_GLOBAL = 2  # fewer available transitions than this: no quotable quantiles
MIN_BUCKET = 20  # thinner age x position buckets fall back to the global quantiles


@dataclass(frozen=True)
class BaselineQuantiles:
    b1: tuple[float, float, float] | None  # global q25/q50/q75 of available multipliers
    b2: tuple[float, float, float] | None  # age-band x position bucket (or B1 fallback)
    b2_fallback: bool


def _quantiles(multipliers: pl.Series) -> tuple[float, float, float]:
    q25, q50, q75 = (multipliers.quantile(q, interpolation="linear") for q in (0.25, 0.5, 0.75))
    assert q25 is not None and q50 is not None and q75 is not None  # len >= MIN_GLOBAL
    return float(q25), float(q50), float(q75)


def compute_baselines(
    universe_t: pl.DataFrame, age: float | None, position_group: str
) -> BaselineQuantiles:
    multipliers = universe_t.get_column("multiplier")
    b1 = _quantiles(multipliers) if multipliers.len() >= MIN_GLOBAL else None

    band = age_band_label(age)
    if band is not None:
        lo, hi = next((lo, hi) for label, lo, hi in AGE_BANDS if label == band)
        bucket = universe_t.filter(
            (pl.col("position_group") == position_group)
            & (pl.col("age_at_transfer") >= lo)
            & (pl.col("age_at_transfer") < hi)
        ).get_column("multiplier")
        if bucket.len() >= MIN_BUCKET:
            return BaselineQuantiles(b1=b1, b2=_quantiles(bucket), b2_fallback=False)
    return BaselineQuantiles(b1=b1, b2=b1, b2_fallback=True)
