"""League-season strength: median derived squad value, log strength, tiers, Elo coverage."""

from __future__ import annotations

import polars as pl

from pipeline.config import (
    MIN_CLUBS_FOR_LEAGUE_STATS,
    TIER_HYSTERESIS_SEASONS,
    TIER_STRENGTH_THRESHOLDS,
)


def assign_display_tiers(
    league_seasons: pl.DataFrame,
    thresholds: tuple[float, float, float] = TIER_STRENGTH_THRESHOLDS,
    hysteresis_seasons: int = TIER_HYSTERESIS_SEASONS,
) -> pl.DataFrame:
    """Tier per league-season from fixed ln-strength thresholds with hysteresis.

    thresholds = (t1, t2, t3), descending: tier 1 when strength >= t1, tier 2
    when >= t2, tier 3 when >= t3, else tier 4. A league's first observed
    season takes its provisional tier outright; afterwards it moves only
    once hysteresis_seasons CONSECUTIVE seasons land in the same different
    tier, so a one-season blip across a cut never relabels a league. A null
    strength (below the membership floor) or a gap in the season sequence
    breaks the chain: the tier is null there and the next valid season
    starts fresh from its provisional tier.

    Fixed thresholds replace rank-quartile bucketing deliberately: quartiles
    force a 31-league season into 8/8/8/7 whatever the value gaps say, which
    kept the single largest strength gap inside tier 1.
    """
    t1, t2, t3 = thresholds

    def provisional(strength: float) -> int:
        return 1 if strength >= t1 else 2 if strength >= t2 else 3 if strength >= t3 else 4

    leagues: list[str] = []
    seasons: list[int] = []
    tiers: list[int | None] = []
    assigned: int | None = None
    run_tier = 0
    run_len = 0
    prev_league: str | None = None
    prev_season: int | None = None
    rows = league_seasons.select("league", "season", "strength").sort(["league", "season"])
    for league, season, strength in rows.iter_rows():
        new_chain = league != prev_league or (prev_season is not None and season - prev_season > 1)
        if new_chain:
            assigned, run_len = None, 0
        if strength is None:
            assigned, run_len = None, 0
            tier = None
        else:
            prov = provisional(strength)
            if assigned is None:
                assigned, run_len = prov, 0
            elif prov == assigned:
                run_len = 0
            else:
                run_len = run_len + 1 if prov == run_tier else 1
                run_tier = prov
                if run_len >= hysteresis_seasons:
                    assigned, run_len = prov, 0
            tier = assigned
        leagues.append(league)
        seasons.append(season)
        tiers.append(tier)
        prev_league, prev_season = league, season

    tier_frame = pl.DataFrame(
        {"league": leagues, "season": seasons, "tier": tiers},
        schema={
            "league": league_seasons.schema["league"],
            "season": league_seasons.schema["season"],
            "tier": pl.Int8(),
        },
    )
    return league_seasons.join(tier_frame, on=["league", "season"], how="left")


def league_seasons(
    club_seasons: pl.DataFrame,
    competitions: pl.DataFrame,
    min_clubs: int = MIN_CLUBS_FOR_LEAGUE_STATS,
    tier_thresholds: tuple[float, float, float] = TIER_STRENGTH_THRESHOLDS,
    hysteresis_seasons: int = TIER_HYSTERESIS_SEASONS,
) -> pl.DataFrame:
    """Per-league-season strength summary from member clubs' derived squad values.

    A league-season with fewer than min_clubs members has no meaningful
    median: strength and tier are null and stats_valid flags it. strength is
    the natural log of the median (null when the median is not positive);
    tier comes from assign_display_tiers (fixed ln-strength thresholds with
    hysteresis — see there). When the input carries an "elo" column,
    median_elo and elo_club_coverage summarise it; otherwise they are
    emitted as null / 0.0 so the output schema is stable.

    league_name (the upstream name slug, e.g. "premier-league") and country
    come from the competitions table so the API can render human labels —
    the two "bundesliga" leagues disambiguate by country. Leagues missing
    from competitions keep nulls. Club-seasons without an honest league
    assignment (league null, source "none") are not members of anything and
    are excluded before aggregation.
    """
    club_seasons = club_seasons.filter(pl.col("league").is_not_null())
    has_elo = "elo" in club_seasons.columns
    aggs: list[pl.Expr] = [
        pl.len().cast(pl.Int64).alias("n_clubs"),
        pl.col("squad_value_eur").median().round(0).cast(pl.Int64).alias("median_squad_value_eur"),
    ]
    if has_elo:
        aggs.append(pl.col("elo").median().cast(pl.Float64).alias("median_elo"))
        aggs.append(
            (pl.col("elo").is_not_null().sum().cast(pl.Float64) / pl.len()).alias(
                "elo_club_coverage"
            )
        )
    grouped = club_seasons.group_by(["league", "season"]).agg(aggs)
    if not has_elo:
        grouped = grouped.with_columns(
            median_elo=pl.lit(None, dtype=pl.Float64),
            elo_club_coverage=pl.lit(0.0, dtype=pl.Float64),
        )
    graded = grouped.with_columns(stats_valid=pl.col("n_clubs") >= min_clubs).with_columns(
        strength=pl.when(pl.col("stats_valid") & (pl.col("median_squad_value_eur") > 0))
        .then(pl.col("median_squad_value_eur").log())
        .otherwise(None)
    )
    tiered = assign_display_tiers(graded, tier_thresholds, hysteresis_seasons)
    labels = competitions.select(
        pl.col("competition_id").alias("league"),
        pl.col("name").alias("league_name"),
        pl.col("country_name").alias("country"),
    )
    return (
        tiered.join(labels, on="league", how="left")
        .select(
            "league",
            "season",
            "n_clubs",
            "median_squad_value_eur",
            "strength",
            "tier",
            "stats_valid",
            "median_elo",
            "elo_club_coverage",
            "league_name",
            "country",
        )
        .sort(["season", "league"])
    )
