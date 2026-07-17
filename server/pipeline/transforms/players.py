"""players.parquet assembly: in-scope players with a dated current market value.

A value is only shown with its as-of date, so the canonical value comes from
the player's latest player_valuations row; players without any valuation
history carry null value AND null date - never a value without a date.
"""

from __future__ import annotations

import polars as pl

from pipeline.transforms.common import covered_league_ids, position_group_expr

PLAYERS_SCHEMA: dict[str, pl.DataType] = {
    "player_id": pl.Int32(),
    "name": pl.String(),
    "position_group": pl.String(),
    "sub_position": pl.String(),
    "date_of_birth": pl.Date(),
    "foot": pl.String(),
    "height_cm": pl.Int16(),
    "current_club_id": pl.Int32(),
    "current_club_name": pl.String(),
    "current_league": pl.String(),
    "market_value_eur": pl.Int64(),
    "market_value_asof": pl.Date(),
    "last_season": pl.Int16(),
}


def assemble_players(
    players: pl.DataFrame, valuations: pl.DataFrame, competitions: pl.DataFrame
) -> pl.DataFrame:
    """One row per player whose current club plays in a covered domestic league."""
    covered = covered_league_ids(competitions)
    latest_value = (
        valuations.filter(
            pl.col("date").is_not_null() & pl.col("market_value_in_eur").is_not_null()
        )
        .sort(["player_id", "date"])
        .group_by("player_id", maintain_order=True)
        .agg(
            market_value_eur=pl.col("market_value_in_eur").last(),
            market_value_asof=pl.col("date").last(),
        )
    )
    return (
        players.filter(pl.col("current_club_domestic_competition_id").is_in(covered))
        .with_columns(position_group_expr())
        .join(latest_value, on="player_id", how="left")
        .select(
            pl.col("player_id").cast(pl.Int32),
            "name",
            "position_group",
            "sub_position",
            "date_of_birth",
            "foot",
            pl.col("height_in_cm").cast(pl.Int16, strict=False).alias("height_cm"),
            pl.col("current_club_id").cast(pl.Int32),
            "current_club_name",
            pl.col("current_club_domestic_competition_id").alias("current_league"),
            pl.col("market_value_eur").cast(pl.Int64),
            "market_value_asof",
            pl.col("last_season").cast(pl.Int16),
        )
        .sort("player_id")
    )
