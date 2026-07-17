"""Per-season profile stats and peer percentiles for player pages.

All stats come from domestic-league appearance rows only. Percentiles are raw
value ranks: higher value = higher percentile for EVERY metric (including
cards and goals conceded) — the presentation layer decides which direction
reads as "good".
"""

from __future__ import annotations

import polars as pl

from pipeline.config import PROFILE_MIN_MINUTES, SEASON_START_MONTH
from pipeline.transforms.common import position_group_expr
from pipeline.transforms.minutes import minutes_share

_KEYS = ["player_id", "season", "league"]
_PEER_GROUP = ["league", "season", "position_group"]
_PCT_METRICS = (
    "goals_p90",
    "assists_p90",
    "ga_p90",
    "cards_p90",
    "conceded_p90",
    "clean_sheet_rate",
)


def _domestic_game_meta(games: pl.DataFrame) -> pl.DataFrame:
    return games.filter(pl.col("competition_type") == "domestic_league").select(
        "game_id", "season", pl.col("competition_id").alias("league")
    )


def player_season_stats(appearances: pl.DataFrame, games: pl.DataFrame) -> pl.DataFrame:
    """Domestic-league counting stats and per-90 rates per (player, season, league).

    Season and league come from the game row, not the appearance. Per-90 rates
    are metric / (minutes / 90), null when minutes == 0.
    """
    joined = appearances.join(_domestic_game_meta(games), on="game_id", how="inner")
    stats = joined.group_by(_KEYS).agg(
        games_played=pl.len().cast(pl.Int64),
        minutes=pl.col("minutes_played").sum(),
        goals=pl.col("goals").sum(),
        assists=pl.col("assists").sum(),
        cards=(pl.col("yellow_cards") + pl.col("red_cards")).sum(),
    )
    per90 = {
        "goals_p90": pl.col("goals"),
        "assists_p90": pl.col("assists"),
        "ga_p90": pl.col("goals") + pl.col("assists"),
        "cards_p90": pl.col("cards"),
    }
    return stats.with_columns(
        [
            pl.when(pl.col("minutes") > 0)
            .then(metric / (pl.col("minutes") / 90.0))
            .otherwise(None)
            .alias(name)
            for name, metric in per90.items()
        ]
    ).sort(_KEYS)


def profile_minutes_share(
    appearances: pl.DataFrame,
    games: pl.DataFrame,
    cleaned_transfers: pl.DataFrame,
    covered_games: pl.DataFrame,
) -> pl.DataFrame:
    """minutes_share per (player, season, league) over the July-June season window.

    The base club is the club of the player's first appearance in that
    league-season; transfer boundaries inside the season split the window, and
    only that league's covered games count toward possible minutes. Nullable
    by design: no covered games means coverage unknown, never zero.
    """
    meta = appearances.join(_domestic_game_meta(games), on="game_id", how="inner")
    keys = (
        meta.sort("date")
        .group_by(_KEYS, maintain_order=True)
        .agg(base_club_id=pl.col("player_club_id").first())
        .with_row_index("anchor_id")
        .with_columns(
            anchor_id=pl.col("anchor_id").cast(pl.Int64),
            window_start=pl.date(pl.col("season"), SEASON_START_MONTH, 1),
            window_end=pl.date(pl.col("season") + 1, SEASON_START_MONTH, 1),
        )
    )
    shares: list[pl.DataFrame] = []
    for (league,) in keys.select("league").unique().sort("league").iter_rows():
        anchors = keys.filter(pl.col("league") == league).select(
            "anchor_id", "player_id", "window_start", "window_end", "base_club_id"
        )
        shares.append(
            minutes_share(
                anchors,
                cleaned_transfers,
                covered_games.filter(pl.col("league") == league),
                appearances,
                [str(league)],
            )
        )
    if not shares:
        return keys.select(*_KEYS).with_columns(minutes_share=pl.lit(None, dtype=pl.Float64))
    return (
        pl.concat(shares)
        .join(keys.select("anchor_id", *_KEYS), on="anchor_id", how="inner")
        .select(*_KEYS, "minutes_share")
        .sort(_KEYS)
    )


def gk_stats(
    appearances: pl.DataFrame, games: pl.DataFrame, club_games: pl.DataFrame
) -> pl.DataFrame:
    """Goalkeeper concession stats per (player, season, league), domestic leagues only.

    opponent_goals is the keeper's club's full-game concession even when the
    keeper played fewer minutes — a documented approximation. Clean-sheet
    attribution requires a full 90 minutes: no credit for partial appearances,
    which are excluded from both clean_sheets and full_games.
    """
    joined = appearances.join(
        club_games.select("game_id", "club_id", "opponent_goals"),
        left_on=["game_id", "player_club_id"],
        right_on=["game_id", "club_id"],
        how="inner",
    ).join(_domestic_game_meta(games), on="game_id", how="inner")
    full = pl.col("minutes_played") >= 90
    return (
        joined.group_by(_KEYS)
        .agg(
            minutes=pl.col("minutes_played").sum(),
            conceded=pl.col("opponent_goals").sum(),
            full_games=full.sum().cast(pl.Int64),
            clean_sheets=(full & (pl.col("opponent_goals") == 0)).sum().cast(pl.Int64),
        )
        .with_columns(
            conceded_p90=pl.when(pl.col("minutes") > 0)
            .then(pl.col("conceded") / (pl.col("minutes") / 90.0))
            .otherwise(None),
            clean_sheet_rate=pl.when(pl.col("full_games") > 0)
            .then(pl.col("clean_sheets") / pl.col("full_games"))
            .otherwise(None),
        )
        .sort(_KEYS)
    )


def assemble_profile_stats(
    stats: pl.DataFrame,
    gk: pl.DataFrame,
    players: pl.DataFrame,
    anchors_share: pl.DataFrame | None = None,
) -> pl.DataFrame:
    """Profile rows with position group, GK-only concession stats and peer percentiles.

    GK columns (conceded_p90, clean_sheet_rate) are kept only for GK rows —
    the outfield join result is discarded. minutes_share is joined when the
    caller supplies it and is a null column otherwise (nullable by design:
    appearance coverage never gates anything). Percentile peers are rows with
    minutes >= PROFILE_MIN_MINUTES within (league, season, position_group);
    pct = (rank - 1) / (n - 1) among peers with a non-null metric, null below
    the floor or when fewer than 2 such peers exist; peer_n is populated for
    every row. Higher raw value = higher percentile for all metrics.
    """
    is_gk = pl.col("position_group") == "GK"
    out = (
        stats.join(
            players.with_columns(position_group_expr()).select("player_id", "position_group"),
            on="player_id",
            how="left",
        )
        .with_columns(pl.col("position_group").fill_null("UNKNOWN"))
        .join(gk.select(*_KEYS, "conceded_p90", "clean_sheet_rate"), on=_KEYS, how="left")
        .with_columns(
            conceded_p90=pl.when(is_gk).then(pl.col("conceded_p90")).otherwise(None),
            clean_sheet_rate=pl.when(is_gk).then(pl.col("clean_sheet_rate")).otherwise(None),
        )
    )
    if anchors_share is None:
        out = out.with_columns(minutes_share=pl.lit(None, dtype=pl.Float64))
    else:
        out = out.join(anchors_share.select(*_KEYS, "minutes_share"), on=_KEYS, how="left")

    in_peer_pool = pl.col("minutes") >= PROFILE_MIN_MINUTES
    out = out.with_columns(peer_n=in_peer_pool.sum().over(_PEER_GROUP).cast(pl.Int16))
    pct_cols: list[pl.Expr] = []
    for metric in _PCT_METRICS:
        rankable = in_peer_pool & pl.col(metric).is_not_null()
        n_rankable = rankable.sum().over(_PEER_GROUP)
        # rank() leaves nulls unranked, so masking non-peers to null ranks peers only
        rank = (
            pl.when(rankable)
            .then(pl.col(metric))
            .otherwise(None)
            .rank(method="average")
            .over(_PEER_GROUP)
        )
        pct_cols.append(
            pl.when(rankable & (n_rankable >= 2))
            .then((rank - 1) / (n_rankable - 1))
            .otherwise(None)
            .alias(f"pct_{metric}")
        )
    return out.with_columns(pct_cols).sort(_KEYS)
