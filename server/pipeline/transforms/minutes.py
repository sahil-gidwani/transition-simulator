"""Playing-time enrichment: minutes_share over an anchor window.

Appearance coverage is uneven by design: many leagues have games with zero
appearance rows, so a game without them must not count as playable time.
minutes features are nullable enrichment and never gate comp eligibility —
a NULL share means "coverage unknown", never zero.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

import polars as pl

_SEGMENT_SCHEMA: dict[str, type[pl.DataType]] = {
    "anchor_id": pl.Int64,
    "club_id": pl.Int64,
    "seg_start": pl.Date,
    "seg_end": pl.Date,
}


def covered_league_games(games: pl.DataFrame, appearances: pl.DataFrame) -> pl.DataFrame:
    """Domestic-league games with at least one appearance row, one row per club side.

    Games with zero appearance rows carry no playing-time signal and are
    excluded from the possible-minutes denominator entirely.
    """
    covered = games.filter(pl.col("competition_type") == "domestic_league").join(
        appearances.select("game_id").unique(), on="game_id", how="semi"
    )
    sides = [
        covered.select(
            "game_id",
            "date",
            "season",
            pl.col("competition_id").alias("league"),
            pl.col(side).alias("club_id"),
        )
        for side in ("home_club_id", "away_club_id")
    ]
    return pl.concat(sides)


def player_segments(anchors: pl.DataFrame, cleaned_transfers: pl.DataFrame) -> pl.DataFrame:
    """Partition each anchor window into club-tenure segments at transfer boundaries.

    Boundaries are the player's transfers strictly inside (window_start,
    window_end). The first segment's club is the first boundary's from-club
    when boundaries exist, else the anchor's base club (a null base yields a
    null-club segment contributing zero possible minutes); each later segment
    takes its boundary's to-club. seg_end is exclusive so a transfer-day game
    counts for the new club, never both.
    """
    boundaries = (
        anchors.select("anchor_id", "player_id", "window_start", "window_end")
        .join(
            cleaned_transfers.select("player_id", "transfer_date", "from_club_id", "to_club_id"),
            on="player_id",
            how="inner",
        )
        .filter(
            (pl.col("transfer_date") > pl.col("window_start"))
            & (pl.col("transfer_date") < pl.col("window_end"))
        )
        .sort(["anchor_id", "transfer_date"])
        .group_by("anchor_id", maintain_order=True)
        .agg(
            dates=pl.col("transfer_date"),
            from_clubs=pl.col("from_club_id"),
            to_clubs=pl.col("to_club_id"),
        )
    )
    joined = anchors.join(boundaries, on="anchor_id", how="left", maintain_order="left")
    rows: list[dict[str, object]] = []
    for row in joined.iter_rows(named=True):
        dates: list[date] = row["dates"] or []
        first_club = row["from_clubs"][0] if dates else row["base_club_id"]
        clubs = [first_club, *(row["to_clubs"] or [])]
        starts = [row["window_start"], *dates]
        ends = [*dates, row["window_end"]]
        rows.extend(
            {"anchor_id": row["anchor_id"], "club_id": club, "seg_start": lo, "seg_end": hi}
            for club, lo, hi in zip(clubs, starts, ends, strict=True)
        )
    return pl.DataFrame(rows, schema=_SEGMENT_SCHEMA).sort(["anchor_id", "seg_start"])


def possible_minutes(segments: pl.DataFrame, covered_games: pl.DataFrame) -> pl.DataFrame:
    """Per anchor: 90 minutes for every covered game of the club held at game date.

    A game counts when its club matches a segment and seg_start <= date <
    seg_end. Anchors matching no covered games return 0 (not null) so callers
    can tell "no covered games" apart from "not computed".
    """
    matched = (
        segments.join(covered_games.select("club_id", "date"), on="club_id", how="inner")
        .filter((pl.col("date") >= pl.col("seg_start")) & (pl.col("date") < pl.col("seg_end")))
        .group_by("anchor_id")
        .agg(n_games=pl.len())
    )
    return (
        segments.select("anchor_id")
        .unique(maintain_order=True)
        .join(matched, on="anchor_id", how="left", maintain_order="left")
        .select(
            "anchor_id",
            possible_minutes=(pl.col("n_games").fill_null(0) * 90).cast(pl.Int64),
        )
    )


def played_minutes(
    anchors: pl.DataFrame, appearances: pl.DataFrame, league_ids: Sequence[str]
) -> pl.DataFrame:
    """Per anchor: minutes actually played in covered leagues within the window.

    Counts appearances of the anchor's player in league_ids with
    window_start <= date < window_end (exclusive upper bound, matching the
    segment convention). Anchors with no appearances return 0.
    """
    apps = appearances.filter(pl.col("competition_id").is_in(list(league_ids))).select(
        "player_id", "date", "minutes_played"
    )
    summed = (
        anchors.select("anchor_id", "player_id", "window_start", "window_end")
        .join(apps, on="player_id", how="inner")
        .filter(
            (pl.col("date") >= pl.col("window_start")) & (pl.col("date") < pl.col("window_end"))
        )
        .group_by("anchor_id")
        .agg(played_minutes=pl.col("minutes_played").sum())
    )
    return (
        anchors.select("anchor_id")
        .join(summed, on="anchor_id", how="left", maintain_order="left")
        .select("anchor_id", played_minutes=pl.col("played_minutes").fill_null(0).cast(pl.Int64))
    )


def minutes_share(
    anchors: pl.DataFrame,
    cleaned_transfers: pl.DataFrame,
    covered_games: pl.DataFrame,
    appearances: pl.DataFrame,
    league_ids: Sequence[str],
) -> pl.DataFrame:
    """Share of possible league minutes played over the anchor window.

    min(played / possible, 1.0), clipped because recorded minutes occasionally
    exceed 90 per game; NULL (never 0.0) when possible == 0 — no covered games
    means coverage is unknown, not that the player sat out. One row per anchor,
    anchor order preserved.
    """
    segments = player_segments(anchors, cleaned_transfers)
    possible = possible_minutes(segments, covered_games)
    played = played_minutes(anchors, appearances, league_ids)
    return (
        anchors.select("anchor_id")
        .join(possible, on="anchor_id", how="left", maintain_order="left")
        .join(played, on="anchor_id", how="left", maintain_order="left")
        .select(
            "anchor_id",
            minutes_share=pl.when(pl.col("possible_minutes") > 0)
            .then((pl.col("played_minutes") / pl.col("possible_minutes")).clip(upper_bound=1.0))
            .otherwise(None)
            .cast(pl.Float64),
        )
    )
