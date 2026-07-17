"""Shared pure derivations: seasons, position groups, coverage, club leagues."""

from __future__ import annotations

from datetime import date

import polars as pl

from pipeline.config import COARSE_POSITION_GROUPS, POSITION_GROUPS, SEASON_START_MONTH


def season_of(col: str) -> pl.Expr:
    """Season label as its starting year, July-June (Jan window belongs to prior label)."""
    d = pl.col(col)
    return (d.dt.year() - (d.dt.month() < SEASON_START_MONTH).cast(pl.Int32)).alias("season")


def season_start(season: int) -> date:
    return date(season, SEASON_START_MONTH, 1)


def position_group_expr() -> pl.Expr:
    """Position group from sub_position, falling back to the coarse position column."""
    return (
        pl.col("sub_position")
        .replace_strict(POSITION_GROUPS, default=None)
        .fill_null(pl.col("position").replace_strict(COARSE_POSITION_GROUPS, default=None))
        .fill_null("UNKNOWN")
        .alias("position_group")
    )


def covered_league_ids(competitions: pl.DataFrame) -> list[str]:
    """Covered domestic league ids (all first-tier leagues present in the dataset)."""
    return sorted(
        competitions.filter(pl.col("type") == "domestic_league")["competition_id"].to_list()
    )


def covered_clubs(clubs: pl.DataFrame, competitions: pl.DataFrame) -> pl.DataFrame:
    """Clubs whose (snapshot) domestic competition is a covered domestic league."""
    leagues = covered_league_ids(competitions)
    return clubs.filter(pl.col("domestic_competition_id").is_in(leagues)).select(
        "club_id", "name", "domestic_competition_id"
    )


def club_league_by_season(games: pl.DataFrame) -> pl.DataFrame:
    """Games-derived league membership: the league a club actually played in.

    One row per (club_id, season): the domestic league the club appeared in
    most that season (ties broken by league code). Only club-seasons with
    match data appear; callers fall back to the clubs.csv snapshot league
    (and record league_source) for the rest.
    """
    league_games = games.filter(pl.col("competition_type") == "domestic_league")
    long = pl.concat(
        [
            league_games.select(
                pl.col("home_club_id").alias("club_id"), "season", pl.col("competition_id")
            ),
            league_games.select(
                pl.col("away_club_id").alias("club_id"), "season", pl.col("competition_id")
            ),
        ]
    )
    counts = long.group_by(["club_id", "season", "competition_id"]).agg(n=pl.len())
    return (
        counts.sort(
            ["club_id", "season", "n", "competition_id"],
            descending=[False, False, True, False],
        )
        .unique(subset=["club_id", "season"], keep="first", maintain_order=True)
        .select("club_id", "season", pl.col("competition_id").alias("league"))
    )
