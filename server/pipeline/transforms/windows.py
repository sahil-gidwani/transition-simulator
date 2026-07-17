"""Valuation windows and outcomes for cleaned transfers, ported from the audit.

One horizon for every comp: v_before is the last valuation in [t-180d, t-1d],
v_after the first in [t+180d, t+540d]. Callers run the funnel chain
clean_transfers -> annotate_scope -> flag_suspected_loans -> attach_v_before
-> attach_v_after -> attach_outcomes; attach_outcomes restores the original
row order (row_idx) that the as-of joins disturb, and compute_funnel
reproduces the audited stage counts the build gates on.
"""

from __future__ import annotations

from datetime import date, timedelta

import polars as pl

from pipeline.config import (
    V_AFTER_MAX_DAYS,
    V_AFTER_MIN_DAYS,
    V_BEFORE_MAX_DAYS,
    FunnelCounts,
)
from pipeline.transforms.transfers import CleaningCounts


def _usable_history(valuations: pl.DataFrame) -> pl.DataFrame:
    """Valuation rows the window joins consume: date and value both present."""
    return valuations.select("player_id", "date", "market_value_in_eur").filter(
        pl.col("date").is_not_null() & pl.col("market_value_in_eur").is_not_null()
    )


def max_valuation_date(valuations: pl.DataFrame) -> date:
    """Latest date in the usable valuation history; drives censoring."""
    value = _usable_history(valuations)["date"].max()
    if not isinstance(value, date):
        raise ValueError("player_valuations carries no dated market values")
    return value


def attach_v_before(tf: pl.DataFrame, valuations: pl.DataFrame) -> pl.DataFrame:
    """v_before/v_before_date: last valuation in [t-180d, t-1d].

    The transfer day itself is excluded so a valuation that already prices the
    move never leaks into the "before" value.
    """
    before = (
        _usable_history(valuations)
        .sort("date")
        .rename({"date": "v_before_date", "market_value_in_eur": "v_before"})
    )
    return (
        tf.with_columns(k_before=pl.col("transfer_date").dt.offset_by("-1d"))
        .sort("k_before")
        .join_asof(
            before,
            left_on="k_before",
            right_on="v_before_date",
            by="player_id",
            strategy="backward",
            tolerance=f"{V_BEFORE_MAX_DAYS - 1}d",  # window [t-180d, t-1d]: strictly before t
        )
        .drop("k_before")
    )


def attach_v_after(tf: pl.DataFrame, valuations: pl.DataFrame) -> pl.DataFrame:
    """v_after/v_after_date: first valuation in [t+180d, t+540d]."""
    after = (
        _usable_history(valuations)
        .sort("date")
        .rename({"date": "v_after_date", "market_value_in_eur": "v_after"})
    )
    return (
        tf.with_columns(k_after=pl.col("transfer_date").dt.offset_by(f"{V_AFTER_MIN_DAYS}d"))
        .sort("k_after")
        .join_asof(
            after,
            left_on="k_after",
            right_on="v_after_date",
            by="player_id",
            strategy="forward",
            tolerance=f"{V_AFTER_MAX_DAYS - V_AFTER_MIN_DAYS}d",  # window [t+180d, t+540d]
        )
        .drop("k_after")
    )


def attach_outcomes(tf: pl.DataFrame, max_val_date: date) -> pl.DataFrame:
    """Censoring flag plus multiplier, delta_pct and days_to_after; restores order.

    A transfer is censored when its v_after window had not opened by the end
    of the valuation history (transfer_date > max_val_date - 180d); equality
    keeps the row observable.
    """
    censor_cutoff = max_val_date - timedelta(days=V_AFTER_MIN_DAYS)
    return (
        tf.with_columns(
            censored=pl.col("transfer_date") > pl.lit(censor_cutoff),
            multiplier=pl.col("v_after") / pl.col("v_before"),
            days_to_after=(pl.col("v_after_date") - pl.col("transfer_date")).dt.total_days(),
        )
        .with_columns(delta_pct=pl.col("multiplier") - 1.0)
        # The as-of joins sorted by the window keys; restore cleaned-transfer order.
        .sort("row_idx")
    )


def compute_funnel(tf: pl.DataFrame, cleaning: CleaningCounts) -> FunnelCounts:
    """Nested funnel stage counts, matching the audited definitions exactly."""
    in_scope = tf.filter(pl.col("in_scope"))
    with_v_before = in_scope.filter(pl.col("v_before").is_not_null())
    observable = with_v_before.filter(~pl.col("censored"))
    with_v_after = observable.filter(pl.col("v_after").is_not_null())
    non_loan = with_v_after.filter(~pl.col("suspected_loan"))
    return FunnelCounts(
        raw=cleaning.raw,
        cleaned=cleaning.cleaned,
        in_scope=in_scope.height,
        with_v_before=with_v_before.height,
        observable=observable.height,
        with_v_after=with_v_after.height,
        non_loan=non_loan.height,
    )
