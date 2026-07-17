"""Structural loan detection: round-trip transfers flagged as suspected loans.

Transfers carry no loan flag upstream, and loans parse to fee=0 exactly like
free transfers - so loans are detected structurally: the same player moving
A->B and then B->A within LOAN_MAX_RETURN_DAYS, with both fees exactly 0.
Buy-backs (any fee > 0) and fee-unknown round-trips stay in the universe.
"""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

from pipeline.config import LOAN_MAX_RETURN_DAYS


@dataclass(frozen=True)
class LoanCounts:
    """Round-trip pairs by class, plus rows flagged (both legs of loan pairs)."""

    loan_pairs: int
    buyback_pairs: int
    ambiguous_pairs: int
    rows_flagged: int


def flag_suspected_loans(tf: pl.DataFrame) -> tuple[pl.DataFrame, LoanCounts]:
    """Add row_idx and suspected_loan; both legs of fee-0/fee-0 round-trips flag.

    Pairing is greedy 1:1 by shortest gap: candidate pairs sort by
    (gap_days, row_idx, row_idx_ret), then each out leg and each return leg is
    used at most once. row_idx stays on the frame: the window as-of joins
    reorder rows and downstream restores the original order by it.
    """
    tf = tf.with_row_index("row_idx")
    legs = tf.select(
        "row_idx", "player_id", "transfer_date", "from_club_id", "to_club_id", "transfer_fee"
    )
    pairs = (
        legs.join(
            legs,
            left_on=["player_id", "to_club_id", "from_club_id"],
            right_on=["player_id", "from_club_id", "to_club_id"],
            how="inner",
            suffix="_ret",
        )
        .filter(pl.col("transfer_date_ret") > pl.col("transfer_date"))
        .with_columns(
            gap_days=(pl.col("transfer_date_ret") - pl.col("transfer_date")).dt.total_days()
        )
        .filter(pl.col("gap_days") <= LOAN_MAX_RETURN_DAYS)
        .sort(["gap_days", "row_idx", "row_idx_ret"])
        .unique(subset=["row_idx"], keep="first", maintain_order=True)
        .unique(subset=["row_idx_ret"], keep="first", maintain_order=True)
        .with_columns(
            pair_class=pl.when((pl.col("transfer_fee") == 0) & (pl.col("transfer_fee_ret") == 0))
            .then(pl.lit("loan"))
            .when((pl.col("transfer_fee") > 0) | (pl.col("transfer_fee_ret") > 0))
            .then(pl.lit("buyback"))
            .otherwise(pl.lit("ambiguous"))
        )
    )
    loan_pairs = pairs.filter(pl.col("pair_class") == "loan")
    loan_rows = sorted(
        set(loan_pairs["row_idx"].to_list()) | set(loan_pairs["row_idx_ret"].to_list())
    )
    tf = tf.with_columns(suspected_loan=pl.col("row_idx").is_in(loan_rows))
    counts = LoanCounts(
        loan_pairs=loan_pairs.height,
        buyback_pairs=pairs.filter(pl.col("pair_class") == "buyback").height,
        ambiguous_pairs=pairs.filter(pl.col("pair_class") == "ambiguous").height,
        rows_flagged=len(loan_rows),
    )
    return tf, counts
