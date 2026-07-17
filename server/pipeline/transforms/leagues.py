"""League-season strength: median derived squad value, log strength, tiers, Elo coverage."""

from __future__ import annotations

import polars as pl


def league_seasons(club_seasons: pl.DataFrame, competitions: pl.DataFrame) -> pl.DataFrame:
    """Per-league-season strength summary from member clubs' derived squad values.

    Tier buckets leagues within each season into quartiles of median squad
    value (1 = strongest; ties broken by league code ascending) — the same
    formula as the audit's tier preview. strength is the natural log of the
    median (null when the median is not positive). When the input carries an
    "elo" column, median_elo and elo_club_coverage summarise it; otherwise
    they are emitted as null / 0.0 so the output schema is stable.

    league_name (the upstream name slug, e.g. "premier-league") and country
    come from the competitions table so the API can render human labels —
    the two "bundesliga" leagues disambiguate by country. Leagues missing
    from competitions keep nulls.
    """
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
    ranked = grouped.sort(
        ["season", "median_squad_value_eur", "league"],
        descending=[False, True, False],
    ).with_columns(
        _rank=pl.int_range(1, pl.len() + 1).over("season"),
        _n=pl.len().over("season"),
    )
    labels = competitions.select(
        pl.col("competition_id").alias("league"),
        pl.col("name").alias("league_name"),
        pl.col("country_name").alias("country"),
    )
    return (
        ranked.with_columns(
            strength=pl.when(pl.col("median_squad_value_eur") > 0)
            .then(pl.col("median_squad_value_eur").log())
            .otherwise(None),
            tier=((pl.col("_rank") - 1) * 4 // pl.col("_n") + 1).cast(pl.Int8),
        )
        .join(labels, on="league", how="left")
        .select(
            "league",
            "season",
            "n_clubs",
            "median_squad_value_eur",
            "strength",
            "tier",
            "median_elo",
            "elo_club_coverage",
            "league_name",
            "country",
        )
        .sort(["season", "league"])
    )
