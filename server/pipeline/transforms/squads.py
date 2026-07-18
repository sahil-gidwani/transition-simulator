"""Derived club strength: squad values from valuations and terciles per league-season.

The upstream clubs table's market-value field is unreliable, so squad value is
always re-derived from player valuations at each season start.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta

import polars as pl

from pipeline.config import MIN_CLUBS_FOR_LEAGUE_STATS, SQUAD_VALUE_STALENESS_DAYS
from pipeline.transforms.common import covered_clubs, season_start

_SQUAD_SCHEMA: dict[str, type[pl.DataType]] = {
    "club_id": pl.Int64,
    "season": pl.Int64,
    "squad_value_eur": pl.Int64,
    "n_valued_players": pl.Int64,
}


def squad_values(valuations: pl.DataFrame, seasons: Sequence[int]) -> pl.DataFrame:
    """Squad value per (club, season), summed from members' valuations at season start.

    A player belongs to a season's squad iff they have a valuation dated on or
    before the season start (July 1) and at most SQUAD_VALUE_STALENESS_DAYS old
    — both edges inclusive, so a valuation exactly 365 days old still counts.
    The player's latest such valuation sets both their club and their value.
    """
    base = valuations.filter(
        pl.col("date").is_not_null()
        & pl.col("market_value_in_eur").is_not_null()
        & pl.col("current_club_id").is_not_null()
    )
    per_season: list[pl.DataFrame] = [pl.DataFrame(schema=_SQUAD_SCHEMA)]
    for season in seasons:
        start = season_start(season)
        eligible = base.filter(
            (pl.col("date") <= start)
            & (pl.col("date") >= start - timedelta(days=SQUAD_VALUE_STALENESS_DAYS))
        )
        # One row per player-date upstream, so sorting by date and keeping the
        # last row per player is a deterministic "latest valuation" pick.
        latest = eligible.sort(["player_id", "date"]).unique(
            subset=["player_id"], keep="last", maintain_order=True
        )
        per_season.append(
            latest.group_by("current_club_id")
            .agg(
                squad_value_eur=pl.col("market_value_in_eur").sum().cast(pl.Int64),
                n_valued_players=pl.len().cast(pl.Int64),
            )
            .rename({"current_club_id": "club_id"})
            .with_columns(season=pl.lit(season, dtype=pl.Int64))
            .select("club_id", "season", "squad_value_eur", "n_valued_players")
        )
    return pl.concat(per_season).sort(["season", "club_id"])


def assemble_club_seasons(
    squads: pl.DataFrame,
    games_leagues: pl.DataFrame,
    clubs: pl.DataFrame,
    competitions: pl.DataFrame,
    min_clubs: int = MIN_CLUBS_FOR_LEAGUE_STATS,
) -> pl.DataFrame:
    """Covered club-seasons with league membership, club name and squad-value tercile.

    League per (club, season) comes from actual games where available
    (league_source="games"). Where a (league, season) has games-derived
    membership at all, that membership is authoritative: a club the games
    put elsewhere (or nowhere) that season is NOT a member, whatever
    today's clubs.csv snapshot says - the snapshot is current-day only and
    padded league-seasons with relegated/defunct "phantom" members. The
    snapshot fallback (league_source="snapshot") survives only for
    league-seasons with no match data at all; club-seasons with no honest
    league assignment keep their row (squad value and Elo stay usable) with
    league=null and league_source="none". Tercile 1 is the top third by
    squad value within (league, season); ties rank the lower club_id first;
    null-league rows and members of league-seasons below min_clubs carry a
    null tercile (a rank within a stub membership is not a strength signal).

    club_value_pct is the continuous version of the tercile: the club's
    squad-value percentile within its (league, season), (n - rank)/(n - 1),
    1.0 = richest (same orientation as elo_pct). It is what separates a
    Real Madrid (far above the league median) from a mid-table budget
    without depending on sparse Elo. Null under exactly the tercile's
    conditions.
    """
    covered = covered_clubs(clubs, competitions).rename(
        {"name": "club_name", "domestic_competition_id": "snapshot_league"}
    )
    games_covered = (
        games_leagues.select(pl.col("league").alias("snapshot_league"), "season")
        .unique()
        .with_columns(snapshot_has_games=pl.lit(True))
    )
    joined = (
        squads.join(covered, on="club_id", how="inner")
        .join(
            games_leagues.rename({"league": "games_league"}),
            on=["club_id", "season"],
            how="left",
        )
        .join(games_covered, on=["snapshot_league", "season"], how="left")
        .with_columns(
            league=pl.coalesce(
                pl.col("games_league"),
                pl.when(~pl.col("snapshot_has_games").fill_null(False)).then(
                    pl.col("snapshot_league")
                ),
            )
        )
        .with_columns(
            league_source=pl.when(pl.col("games_league").is_not_null())
            .then(pl.lit("games"))
            .when(pl.col("league").is_not_null())
            .then(pl.lit("snapshot"))
            .otherwise(pl.lit("none")),
        )
    )
    ranked = joined.sort(
        ["league", "season", "squad_value_eur", "club_id"],
        descending=[False, False, True, False],
    ).with_columns(
        _rank=pl.int_range(1, pl.len() + 1).over(["league", "season"]),
        _n=pl.len().over(["league", "season"]),
    )
    stats_ok = pl.col("league").is_not_null() & (pl.col("_n") >= min_clubs)
    return (
        ranked.with_columns(
            tercile=pl.when(stats_ok)
            .then((pl.col("_rank") - 1) * 3 // pl.col("_n") + 1)
            .cast(pl.Int8),
            club_value_pct=pl.when(stats_ok & (pl.col("_n") > 1))
            .then((pl.col("_n") - pl.col("_rank")) / (pl.col("_n") - 1))
            .cast(pl.Float32),
        )
        .select(
            "club_id",
            "season",
            "club_name",
            "league",
            "league_source",
            "squad_value_eur",
            "n_valued_players",
            "tercile",
            "club_value_pct",
        )
        .sort(["season", "league", "club_id"])
    )
