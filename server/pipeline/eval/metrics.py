"""Backtest metrics: pinball, coverage, width, MdAPE, segmentation.

Everything reads the per-query records frame. Pinball is computed on the
LOG multiplier as the primary metric: multipliers are heavily right-skewed,
the log makes a 2x overshoot and a 0.5x undershoot cost the same, and
quantiles are monotone-equivariant - ln(q_tau) IS the tau-quantile of the
log target for every method, so Precedent, the naive baselines and the
skyline compare apples-to-apples. Raw-multiplier pinball is kept as a
secondary column for interpretability.

A method is "scored" on a query when its q50 is non-null; for Precedent
that is exactly the not-insufficient rows. Refusals are reported as a rate
next to every cell, never hidden.
"""

from __future__ import annotations

import polars as pl

TAUS: tuple[float, float, float] = (0.25, 0.50, 0.75)

# Half-open bands [lo, hi); fractional ages land with their birthday age.
AGE_BANDS: tuple[tuple[str, float, float], ...] = (
    ("<22", 0.0, 22.0),
    ("22-25", 22.0, 26.0),
    ("26-29", 26.0, 30.0),
    ("30+", 30.0, 200.0),
)
VALUE_BRACKETS: tuple[tuple[str, int, int], ...] = (
    ("<1M", 0, 1_000_000),
    ("1-5M", 1_000_000, 5_000_000),
    ("5-15M", 5_000_000, 15_000_000),
    (">=15M", 15_000_000, 10_000_000_000),
)

SEGMENT_COLUMNS: tuple[str, ...] = ("age_band", "position_group", "tier_jump", "value_bracket")


def age_band_label(age: float | None) -> str | None:
    if age is None:
        return None
    for label, lo, hi in AGE_BANDS:
        if lo <= age < hi:
            return label
    return None


def _banded(col: pl.Expr, bands: tuple[tuple[str, float, float], ...]) -> pl.Expr:
    # Reversed fold of complete when/then/otherwise expressions; a null value
    # fails every band condition and falls through to the null default.
    expr: pl.Expr = pl.lit(None, dtype=pl.String)
    for label, lo, hi in reversed(bands):
        expr = pl.when((col >= lo) & (col < hi)).then(pl.lit(label)).otherwise(expr)
    return expr


def add_segments(records: pl.DataFrame) -> pl.DataFrame:
    """Reporting cells: age band, value bracket, tier-jump direction."""
    value_bands = tuple((label, float(lo), float(hi)) for label, lo, hi in VALUE_BRACKETS)
    return records.with_columns(
        age_band=_banded(pl.col("age_at_transfer"), AGE_BANDS),
        value_bracket=_banded(pl.col("v_before"), value_bands),
        tier_jump=pl.when(pl.col("from_tier").is_null())
        .then(pl.lit("unknown"))
        .when(pl.col("to_tier") < pl.col("from_tier"))
        .then(pl.lit("up"))
        .when(pl.col("to_tier") > pl.col("from_tier"))
        .then(pl.lit("down"))
        .otherwise(pl.lit("same")),
    )


def _pinball(y: pl.Expr, yhat: pl.Expr, tau: float) -> pl.Expr:
    diff = y - yhat
    return pl.when(diff >= 0).then(tau * diff).otherwise((tau - 1) * diff)


def aggregate(
    records: pl.DataFrame,
    by: list[str],
    q25: str = "q25",
    q50: str = "q50",
    q75: str = "q75",
    min_cell: int = 100,
) -> pl.DataFrame:
    """One row per cell (pooled when `by` is empty), most-populated first.

    Cells under `min_cell` carry suppressed=True so reports can fold them
    into a single explicit line instead of silently dropping them.
    """
    actual = pl.col("actual_multiplier")
    y_log = actual.log()
    scored = pl.col(q50).is_not_null()
    covered = (pl.col(q25) <= actual) & (actual <= pl.col(q75))  # endpoints inclusive
    width = pl.col(q75).log() - pl.col(q25).log()
    ape = (pl.col(q50) - actual).abs() / actual

    frame, keys = (records, by) if by else (records.with_columns(cell=pl.lit("all")), ["cell"])
    pin_log = {
        f"pinball_{int(tau * 100)}": _pinball(y_log, pl.col(col).log(), tau).filter(scored).mean()
        for tau, col in zip(TAUS, (q25, q50, q75), strict=True)
    }
    pin_raw = [
        _pinball(actual, pl.col(col), tau).filter(scored).mean()
        for tau, col in zip(TAUS, (q25, q50, q75), strict=True)
    ]
    out = (
        frame.group_by(keys)
        .agg(
            n_total=pl.len(),
            n_scored=scored.sum(),
            coverage=covered.filter(scored).mean(),
            width_mean=width.filter(scored).mean(),
            width_median=width.filter(scored).median(),
            mdape=ape.filter(scored).median(),
            **pin_log,
            pinball_raw_mean=(pin_raw[0] + pin_raw[1] + pin_raw[2]) / 3,
        )
        .with_columns(
            insufficient_rate=1.0 - pl.col("n_scored") / pl.col("n_total"),
            pinball_mean=(pl.col("pinball_25") + pl.col("pinball_50") + pl.col("pinball_75")) / 3,
            suppressed=pl.col("n_total") < min_cell,
        )
        .sort(["n_total", *keys], descending=[True, *(False for _ in keys)])
    )
    return out.drop("cell") if not by else out
