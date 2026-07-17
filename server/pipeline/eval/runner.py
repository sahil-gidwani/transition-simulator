"""The real-service backtest loop.

Every held-out transition runs through the exact serving code path -
find_comps + summarize_pool - against the availability-filtered universe,
so the recorded numbers describe the shipped engine, not a re-implementation.
Deterministic by construction: no RNG, stable iteration order, stable sorts.
"""

from __future__ import annotations

import polars as pl

from app.repositories.store import DataStore
from app.services.comps import find_comps
from app.services.constants import DEFAULT_RETRIEVAL, RetrievalConfig
from app.services.valuation import summarize_pool
from pipeline.eval.availability import available_universe
from pipeline.eval.baselines import compute_baselines
from pipeline.eval.contexts import SkippedQuery, build_eval_query
from pipeline.eval.records import PredictionRecord, records_frame
from pipeline.eval.splits import eval_rows


def _triple(
    quantiles: tuple[float, float, float] | None,
) -> tuple[float | None, float | None, float | None]:
    return quantiles if quantiles is not None else (None, None, None)


def run_backtest(
    store: DataStore,
    seasons: tuple[int, ...],
    config: RetrievalConfig = DEFAULT_RETRIEVAL,
    club_level: bool = True,
) -> tuple[pl.DataFrame, list[SkippedQuery]]:
    """Simulate every eval-season transition as-of its transfer date.

    club_level=False is the league-only ablation: the actual destination
    club is withheld, so club-side distance terms drop exactly as they do
    for a live league-level simulation.
    """
    universe = store.transitions.comps_universe
    strengths = store.seasons.strength_frame()
    season_min = store.build_info.season_min
    records: list[PredictionRecord] = []
    skips: list[SkippedQuery] = []
    for row in eval_rows(universe, seasons).iter_rows(named=True):
        built = build_eval_query(row, store.seasons)
        if isinstance(built, SkippedQuery):
            skips.append(built)
            continue
        universe_t = available_universe(universe, built.transfer_date)
        result = find_comps(
            built.query,
            built.dest_league,
            built.dest_club if club_level else None,
            universe_t,
            strengths,
            season_min,
            config=config,
        )
        value_range, confidence = summarize_pool(
            result.pool, built.query.value_eur, result.quality.relaxation_level
        )
        baselines = compute_baselines(universe_t, built.query.age, built.position_group)
        b1_q25, b1_q50, b1_q75 = _triple(baselines.b1)
        b2_q25, b2_q50, b2_q75 = _triple(baselines.b2)
        records.append(
            PredictionRecord(
                player_id=built.player_id,
                transfer_date=built.transfer_date,
                season=built.season,
                v_before=built.v_before,
                v_after=built.v_after,
                actual_multiplier=built.actual_multiplier,
                q25=value_range.q25_multiplier if value_range is not None else None,
                q50=value_range.q50_multiplier if value_range is not None else None,
                q75=value_range.q75_multiplier if value_range is not None else None,
                insufficient=value_range is None,
                pool_size=len(result.pool),
                relaxation_level=result.quality.relaxation_level,
                confidence=confidence,
                iqr_log=value_range.iqr_log if value_range is not None else None,
                n_available=universe_t.height,
                b1_q25=b1_q25,
                b1_q50=b1_q50,
                b1_q75=b1_q75,
                b2_q25=b2_q25,
                b2_q50=b2_q50,
                b2_q75=b2_q75,
                b2_fallback=baselines.b2_fallback,
                age_at_transfer=built.age_at_transfer,
                position_group=built.position_group,
                from_tier=built.from_tier,
                to_tier=built.to_tier,
                minutes_known=built.minutes_known,
            )
        )
    return records_frame(records), skips
