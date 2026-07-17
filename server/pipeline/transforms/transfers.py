"""Transfer cleaning and scope annotation, ported from the audited funnel.

Callers run the funnel chain in this order: clean_transfers -> annotate_scope
-> flag_suspected_loans (loans.py) -> attach_v_before -> attach_v_after ->
attach_outcomes (windows.py). compute_funnel (windows.py) then reproduces the
audited stage counts, which the build gates on exactly.
"""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

from pipeline.config import PSEUDO_CLUB_PATTERN
from pipeline.transforms.common import season_of


@dataclass(frozen=True)
class CleaningCounts:
    """Row counts through cleaning; raw and cleaned feed the funnel parity gate."""

    raw: int
    with_date: int
    dupes_removed: int
    self_transfers_removed: int
    cleaned: int


def clean_transfers(transfers: pl.DataFrame) -> tuple[pl.DataFrame, CleaningCounts]:
    """Drop undated rows, (player, date) duplicates, and self-transfers.

    Duplicates keep the first row after sorting by player, date and club ids;
    self-transfer removal keeps rows with a null club id on either side.
    """
    raw = transfers.height
    tf = transfers.filter(pl.col("transfer_date").is_not_null())
    with_date = tf.height
    tf = tf.sort(["player_id", "transfer_date", "from_club_id", "to_club_id"])

    n = tf.height
    tf = tf.unique(subset=["player_id", "transfer_date"], keep="first", maintain_order=True)
    dupes_removed = n - tf.height

    n = tf.height
    tf = tf.filter(
        pl.col("from_club_id").is_null()
        | pl.col("to_club_id").is_null()
        | (pl.col("from_club_id") != pl.col("to_club_id"))
    )
    counts = CleaningCounts(
        raw=raw,
        with_date=with_date,
        dupes_removed=dupes_removed,
        self_transfers_removed=n - tf.height,
        cleaned=tf.height,
    )
    return tf, counts


def annotate_scope(cleaned: pl.DataFrame, covered_ids: list[int]) -> pl.DataFrame:
    """Add scope flags, pseudo-club flag and season to cleaned transfers.

    in_scope means both clubs play in a covered domestic league; pseudo-club
    rows ("Retired", "Without Club", ...) are flagged for reporting only.
    """
    covered = sorted(covered_ids)
    tf = cleaned.with_columns(
        from_in_scope=pl.col("from_club_id").is_in(covered),
        to_in_scope=pl.col("to_club_id").is_in(covered),
        pseudo_club=(
            pl.col("from_club_name").str.contains(PSEUDO_CLUB_PATTERN).fill_null(False)
            | pl.col("to_club_name").str.contains(PSEUDO_CLUB_PATTERN).fill_null(False)
        ),
        season=season_of("transfer_date"),
    )
    return tf.with_columns(in_scope=pl.col("from_in_scope") & pl.col("to_in_scope"))
