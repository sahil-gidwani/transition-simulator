"""Comp matching: hard filters, weighted-distance ranking, relaxation ladder.

Comps are selected by similarity ONLY - outcomes (multiplier, delta) never
enter the distance, so decliners surface exactly as often as their similarity
earns (no survivorship bias). Every null has an explicit policy: a null on
the query side skips the affected filter/term (and is flagged in
pool_quality); a null on the comp side fails an active hard filter naturally
and drops ranking terms per comp with weight renormalization.
"""

from __future__ import annotations

import math
import operator
from dataclasses import dataclass
from datetime import date
from functools import reduce
from typing import Any

import polars as pl

from app.core.clock import Clock
from app.core.errors import ApiError
from app.repositories.players import PlayerRecord
from app.repositories.seasons import ClubSeason, LeagueSeason
from app.repositories.store import DataStore
from app.services.constants import (
    AGE_SCALE,
    DEFAULT_RETRIEVAL,
    LN_VALUE_SCALE,
    RECENCY_SCALE,
    STRENGTH_SCALE,
    TERCILE_SCALE,
    LadderStep,
    RetrievalConfig,
)


@dataclass(frozen=True)
class QueryContext:
    """The player side of a simulation, resolved once."""

    player: PlayerRecord
    value_eur: int
    age: float | None
    origin_tier: int | None
    origin_strength: float | None
    origin_tercile: int | None
    minutes_share: float | None
    latest_season: int


@dataclass(frozen=True)
class ScoredComp:
    player_id: int
    player_name: str
    transfer_date: date
    season: int
    age_at_transfer: float | None
    sub_position: str | None
    from_club_name: str
    to_club_name: str
    from_league: str | None  # null when the origin filter was dropped (last ladder level)
    to_league: str
    v_before: int
    v_after: int
    multiplier: float
    delta_pct: float
    distance: float
    similarity: float
    tags: list[str]
    elo_term_used: bool


@dataclass(frozen=True)
class PoolQuality:
    pool_size: int
    relaxation_level: int
    relaxation_steps: list[str]
    expanded_search: bool
    club_selected: bool
    elo_pool_coverage: float
    dest_elo_available: bool
    missing_age: bool
    missing_minutes: bool
    origin_tier_unknown: bool


@dataclass(frozen=True)
class CompsResult:
    pool: list[ScoredComp]
    quality: PoolQuality


def build_query_context(player: PlayerRecord, store: DataStore, clock: Clock) -> QueryContext:
    # <= 0 guards a future data vintage shipping upstream's 0 sentinel as a
    # latest value: that must stay a 409, never a math.log domain error.
    if player.market_value_eur is None or player.market_value_eur <= 0:
        raise ApiError(
            409,
            "player_without_value",
            f"{player.name} has no market valuation on record - a simulation needs a "
            "current value to anchor the predicted range",
        )
    age: float | None = None
    if player.date_of_birth is not None:
        age = (clock.today() - player.date_of_birth).days / 365.25
    league = store.seasons.league_latest(player.current_league)
    club = store.seasons.club_latest(player.current_club_id)
    return QueryContext(
        player=player,
        value_eur=player.market_value_eur,
        age=age,
        origin_tier=league.tier if league is not None else None,
        origin_strength=league.strength if league is not None else None,
        origin_tercile=club.tercile if club is not None else None,
        minutes_share=store.profiles.latest_minutes_share(player.player_id),
        latest_season=store.seasons.latest_season,
    )


def _hard_filter(
    universe: pl.DataFrame,
    query: QueryContext,
    dest_tier: int,
    step: LadderStep,
    season_min: int,
) -> pl.DataFrame:
    """Polars null semantics do the null policy for free: a null comp value
    fails any active comparison and the row drops."""
    conds = [
        pl.col("position_group") == query.player.position_group,
        pl.col("season") >= season_min,
        pl.col("to_tier") == dest_tier,
    ]
    if query.age is not None:
        conds.append(
            pl.col("age_at_transfer").is_between(
                query.age - step.age_band, query.age + step.age_band
            )
        )
    # Bracket the raw v_before instead of a computed ratio: polars evaluates
    # int/int division via reciprocal multiplication, so an exact-edge comp
    # (ratio 0.4) lands at 0.3999... and would drop. The 1e-9 relative slack
    # is far below the euro granularity of market values.
    lo, hi = step.value_bracket
    conds.append(
        pl.col("v_before").is_between(
            lo * query.value_eur * (1 - 1e-9), hi * query.value_eur * (1 + 1e-9)
        )
    )
    if step.origin_tier_band is not None and query.origin_tier is not None:
        conds.append((pl.col("from_tier") - query.origin_tier).abs() <= step.origin_tier_band)
    return universe.filter(reduce(operator.and_, conds))


def _distance_terms(
    query: QueryContext,
    dest_league: LeagueSeason,
    dest_club: ClubSeason | None,
    drop_club_terms: bool,
    config: RetrievalConfig,
) -> list[tuple[pl.Expr, float]]:
    terms: list[tuple[pl.Expr, float]] = [
        (
            (pl.col("v_before").log() - math.log(query.value_eur)).abs() / LN_VALUE_SCALE,
            config.w_log_value,
        )
    ]
    if query.age is not None:
        terms.append(((pl.col("age_at_transfer") - query.age).abs() / AGE_SCALE, config.w_age))
    if dest_league.strength is not None:
        terms.append(
            (
                (pl.col("to_strength") - dest_league.strength).abs() / STRENGTH_SCALE,
                config.w_dest_strength,
            )
        )
    if query.origin_strength is not None:
        terms.append(
            (
                (pl.col("from_strength") - query.origin_strength).abs() / STRENGTH_SCALE,
                config.w_origin_strength,
            )
        )
    if not drop_club_terms and dest_club is not None:
        if dest_club.elo_pct is not None:
            terms.append(((pl.col("to_elo_pct") - dest_club.elo_pct).abs(), config.w_elo))
        if dest_club.tercile is not None:
            terms.append(
                (
                    (pl.col("to_tercile") - dest_club.tercile).abs() / TERCILE_SCALE,
                    config.w_dest_tercile,
                )
            )
    if not drop_club_terms and query.origin_tercile is not None:
        terms.append(
            (
                (pl.col("from_tercile") - query.origin_tercile).abs() / TERCILE_SCALE,
                config.w_origin_tercile,
            )
        )
    if query.minutes_share is not None:
        terms.append(((pl.col("minutes_share_pre") - query.minutes_share).abs(), config.w_minutes))
    if query.player.sub_position is not None:
        terms.append(
            (
                (pl.col("sub_position") != query.player.sub_position).cast(pl.Float64),
                config.w_sub_position,
            )
        )
    terms.append((((query.latest_season - pl.col("season")) / RECENCY_SCALE), config.w_recency))
    return terms


def _score(
    filtered: pl.DataFrame,
    query: QueryContext,
    dest_league: LeagueSeason,
    dest_club: ClubSeason | None,
    drop_club_terms: bool,
    strengths: pl.DataFrame,
    config: RetrievalConfig,
) -> pl.DataFrame:
    """Renormalized weighted distance: per comp, missing terms drop from both
    the numerator and the weight mass, so a null never penalizes."""
    season32 = pl.col("season").cast(pl.Int16)
    with_strengths = filtered.join(
        strengths.select(
            to_league=pl.col("league"), season=season32, to_strength=pl.col("strength")
        ),
        on=["to_league", "season"],
        how="left",
    ).join(
        strengths.select(
            from_league=pl.col("league"), season=season32, from_strength=pl.col("strength")
        ),
        on=["from_league", "season"],
        how="left",
    )
    terms = _distance_terms(query, dest_league, dest_club, drop_club_terms, config)
    # Terms over Float32 source columns (age, elo, minutes) would otherwise
    # multiply by the weight in Float32; cast so the whole distance is
    # uniform double-precision arithmetic.
    numerator = reduce(
        operator.add,
        [pl.when(d.is_not_null()).then(d.cast(pl.Float64) * w).otherwise(0.0) for d, w in terms],
    )
    weight_mass = reduce(
        operator.add,
        [pl.when(d.is_not_null()).then(pl.lit(w)).otherwise(0.0) for d, w in terms],
    )
    elo_active = (
        pl.col("to_elo_pct").is_not_null()
        if not drop_club_terms and dest_club is not None and dest_club.elo_pct is not None
        else pl.lit(False)
    )
    return with_strengths.with_columns(
        distance=(numerator / weight_mass).cast(pl.Float64),
        elo_term_used=elo_active,
    )


def _tags(
    row: dict[str, Any],
    query: QueryContext,
    dest_club: ClubSeason | None,
    drop_club_terms: bool,
) -> list[str]:
    tags: list[str] = []
    if 0.8 <= row["v_before"] / query.value_eur <= 1.25:
        tags.append("similar market value")
    if (
        query.age is not None
        and row["age_at_transfer"] is not None
        and abs(row["age_at_transfer"] - query.age) <= 1.5
    ):
        tags.append("same age profile")
    if query.player.sub_position is not None and row["sub_position"] == query.player.sub_position:
        tags.append(f"same sub-position ({row['sub_position']})")
    if not drop_club_terms and dest_club is not None:
        if (
            dest_club.elo_pct is not None
            and row["to_elo_pct"] is not None
            and abs(row["to_elo_pct"] - dest_club.elo_pct) <= 0.15
        ):
            tags.append("destination club strength alike")
        if row["to_tercile"] == dest_club.tercile:
            tags.append("same destination club tier")
    if (
        query.minutes_share is not None
        and row["minutes_share_pre"] is not None
        and abs(row["minutes_share_pre"] - query.minutes_share) <= 0.15
    ):
        tags.append("similar playing time")
    if row["season"] >= query.latest_season - 2:
        tags.append("recent move")
    if not tags:
        tags.append("closest available precedent")
    return tags


def find_comps(
    query: QueryContext,
    dest_league: LeagueSeason,
    dest_club: ClubSeason | None,
    universe: pl.DataFrame,
    strengths: pl.DataFrame,
    season_min: int,
    config: RetrievalConfig = DEFAULT_RETRIEVAL,
) -> CompsResult:
    level = 0
    step = config.ladder[0]
    filtered = _hard_filter(universe, query, dest_league.tier, step, season_min)
    for level, step in enumerate(config.ladder):  # noqa: B007 - level/step used after the loop
        filtered = _hard_filter(universe, query, dest_league.tier, step, season_min)
        if filtered.height >= config.min_pool_target:
            break

    scored = _score(
        filtered, query, dest_league, dest_club, step.drop_club_terms, strengths, config
    )
    pool_df = scored.sort(["distance", "player_id", "transfer_date"]).head(config.pool_k)

    pool = [
        ScoredComp(
            player_id=row["player_id"],
            player_name=row["player_name"],
            transfer_date=row["transfer_date"],
            season=row["season"],
            age_at_transfer=row["age_at_transfer"],
            sub_position=row["sub_position"],
            from_club_name=row["from_club_name"],
            to_club_name=row["to_club_name"],
            from_league=row["from_league"],
            to_league=row["to_league"],
            v_before=row["v_before"],
            v_after=row["v_after"],
            multiplier=row["multiplier"],
            delta_pct=row["delta_pct"],
            distance=row["distance"],
            similarity=math.exp(-row["distance"]),
            tags=_tags(row, query, dest_club, step.drop_club_terms),
            elo_term_used=row["elo_term_used"],
        )
        for row in pool_df.iter_rows(named=True)
    ]
    elo_used = sum(1 for comp in pool if comp.elo_term_used)
    quality = PoolQuality(
        pool_size=len(pool),
        relaxation_level=level,
        relaxation_steps=[config.ladder[i].label for i in range(1, level + 1)],
        expanded_search=level > 0,
        club_selected=dest_club is not None,
        elo_pool_coverage=elo_used / len(pool) if pool else 0.0,
        dest_elo_available=dest_club is not None and dest_club.elo_pct is not None,
        missing_age=query.age is None,
        missing_minutes=query.minutes_share is None,
        origin_tier_unknown=query.origin_tier is None,
    )
    return CompsResult(pool=pool, quality=quality)
