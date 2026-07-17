"""transitions.parquet assembly: qualifying transfers with all enrichment joined.

A qualifying transfer is in scope with both v_before and v_after observed, from
season 2012/13 on. Suspected loans stay in the artifact behind their flag (the
comps universe excludes them downstream); enrichment columns are nullable and
never drop a row.
"""

from __future__ import annotations

import polars as pl

from pipeline.config import MINUTES_WINDOW_DAYS, SEASON_MIN
from pipeline.transforms.common import position_group_expr

TRANSITIONS_SCHEMA: dict[str, pl.DataType] = {
    "player_id": pl.Int32(),
    "player_name": pl.String(),
    "transfer_date": pl.Date(),
    "season": pl.Int16(),
    "age_at_transfer": pl.Float32(),
    "position_group": pl.String(),
    "sub_position": pl.String(),
    "from_club_id": pl.Int32(),
    "to_club_id": pl.Int32(),
    "from_club_name": pl.String(),
    "to_club_name": pl.String(),
    "from_league": pl.String(),
    "to_league": pl.String(),
    "from_tier": pl.Int8(),
    "to_tier": pl.Int8(),
    "from_tercile": pl.Int8(),
    "to_tercile": pl.Int8(),
    "from_elo": pl.Float32(),
    "from_elo_pct": pl.Float32(),
    "to_elo": pl.Float32(),
    "to_elo_pct": pl.Float32(),
    "v_before": pl.Int64(),
    "v_before_date": pl.Date(),
    "v_after": pl.Int64(),
    "v_after_date": pl.Date(),
    "multiplier": pl.Float64(),
    "delta_pct": pl.Float64(),
    "days_to_after": pl.Int16(),
    "transfer_fee_eur": pl.Int64(),
    "minutes_share_pre": pl.Float32(),
    "suspected_loan": pl.Boolean(),
}


def filter_universe_rows(tf: pl.DataFrame) -> pl.DataFrame:
    """Qualifying rows: in scope, both window values observed, season >= 2012/13.

    Loans are kept (flagged); censored rows are excluded implicitly because no
    valuation can exist 180+ days past the end of the valuation history.
    """
    return tf.filter(
        pl.col("in_scope")
        & pl.col("v_before").is_not_null()
        & pl.col("v_after").is_not_null()
        & (pl.col("season") >= SEASON_MIN)
    )


def attach_player_attrs(tf: pl.DataFrame, players: pl.DataFrame) -> pl.DataFrame:
    """Age at transfer and position group, from the players table."""
    attrs = players.select("player_id", "date_of_birth", "sub_position", "position")
    return (
        tf.join(attrs, on="player_id", how="left")
        .with_columns(
            age_at_transfer=(
                (pl.col("transfer_date") - pl.col("date_of_birth")).dt.total_days() / 365.25
            ),
        )
        .with_columns(position_group_expr())
    )


def minutes_anchors(rows: pl.DataFrame) -> pl.DataFrame:
    """One minutes_share anchor per transition: the 365 days before the transfer.

    window_end is the transfer date itself (exclusive), so the window is
    [t-365d, t-1d]; the base club is the transition's origin club.
    """
    return rows.select(
        anchor_id=pl.col("row_idx").cast(pl.Int64),
        player_id=pl.col("player_id"),
        window_start=pl.col("transfer_date").dt.offset_by(f"-{MINUTES_WINDOW_DAYS}d"),
        window_end=pl.col("transfer_date"),
        base_club_id=pl.col("from_club_id"),
    )


def elo_keys(rows: pl.DataFrame, side: str) -> pl.DataFrame:
    """(club_id, asof_date) keys for one side of the move, tagged by row_idx."""
    return rows.select(
        row_idx=pl.col("row_idx"),
        club_id=pl.col(f"{side}_club_id"),
        asof_date=pl.col("transfer_date"),
    )


def _side_context(
    club_seasons: pl.DataFrame, league_seasons: pl.DataFrame, side: str
) -> tuple[pl.DataFrame, pl.DataFrame]:
    club_part = club_seasons.select(
        pl.col("club_id").alias(f"{side}_club_id"),
        "season",
        pl.col("league").alias(f"{side}_league"),
        pl.col("tercile").alias(f"{side}_tercile"),
    )
    league_part = league_seasons.select(
        pl.col("league").alias(f"{side}_league"),
        "season",
        pl.col("tier").alias(f"{side}_tier"),
    )
    return club_part, league_part


def assemble_transitions(
    rows: pl.DataFrame,
    club_seasons: pl.DataFrame,
    league_seasons: pl.DataFrame,
    minutes: pl.DataFrame,
    elo_from: pl.DataFrame,
    elo_to: pl.DataFrame,
) -> pl.DataFrame:
    """Join league/tier/tercile, transfer-date Elo and minutes share; cast the schema.

    rows must already carry player attrs (attach_player_attrs); minutes maps
    anchor_id (=row_idx) to minutes_share; elo_from/elo_to are elo_asof outputs
    keyed by row_idx.
    """
    out = rows
    for side in ("from", "to"):
        club_part, league_part = _side_context(club_seasons, league_seasons, side)
        out = out.join(club_part, on=[f"{side}_club_id", "season"], how="left")
        out = out.join(league_part, on=[f"{side}_league", "season"], how="left")
    out = out.join(
        elo_from.select("row_idx", from_elo=pl.col("elo"), from_elo_pct=pl.col("elo_pct")),
        on="row_idx",
        how="left",
    ).join(
        elo_to.select("row_idx", to_elo=pl.col("elo"), to_elo_pct=pl.col("elo_pct")),
        on="row_idx",
        how="left",
    )
    out = out.join(
        minutes.select(
            pl.col("anchor_id").alias("row_idx").cast(out.schema["row_idx"]),
            minutes_share_pre=pl.col("minutes_share"),
        ),
        on="row_idx",
        how="left",
    )
    out = out.with_columns(
        transfer_fee_eur=pl.col("transfer_fee").round(0).cast(pl.Int64, strict=False)
    )
    return out.select(
        *(pl.col(name).cast(dtype) for name, dtype in TRANSITIONS_SCHEMA.items())
    ).sort(["transfer_date", "player_id"])
