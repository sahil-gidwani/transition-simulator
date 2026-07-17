"""Confidence-threshold selection and the calibration decision.

Both read post-freeze VALIDATION records only - test seasons are never
touched here. Confidence tiers partition rather than rank, so they are not
pinball-tunable: a small grid is searched for "honest" settings, where a
tier's empirical coverage brackets the nominal 50% and higher confidence
means narrower ranges. Calibration then decides, from validation coverage,
whether reported endpoints need per-tier widening; endpoints are recomputed
from the stored pools, so they remain order statistics of the shown comps.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import product
from typing import Any

import polars as pl

from app.services import constants
from app.services.valuation import weighted_quantile

HIGH_MIN_POOL_GRID = (8, 12, 16)
HIGH_MAX_IQR_GRID = (0.25, 0.35, 0.45)
HIGH_MAX_RELAX_GRID = (0, 1)
MED_MIN_POOL_GRID = (4, 6, 8)
MED_MAX_IQR_GRID = (0.5, 0.6, 0.8)
MED_MAX_RELAX_GRID = (2, 3)

HIGH_COVERAGE_BAND = (0.45, 0.55)
MED_COVERAGE_BAND = (0.42, 0.58)
MIN_TIER_N = 100

CAL_TRIGGER_BAND = (0.45, 0.55)  # pooled validation coverage outside this: calibrate
CAL_DELTA_GRID = tuple(i / 100 for i in range(16))  # 0.00 .. 0.15


@dataclass(frozen=True)
class ConfThresholds:
    high_min_pool: int
    high_max_iqr_log: float
    high_max_relaxation: int
    med_min_pool: int
    med_max_iqr_log: float
    med_max_relaxation: int


def hand_set_thresholds() -> ConfThresholds:
    return ConfThresholds(
        high_min_pool=constants.CONF_HIGH_MIN_POOL,
        high_max_iqr_log=constants.CONF_HIGH_MAX_IQR_LOG,
        high_max_relaxation=constants.CONF_HIGH_MAX_RELAXATION,
        med_min_pool=constants.CONF_MED_MIN_POOL,
        med_max_iqr_log=constants.CONF_MED_MAX_IQR_LOG,
        med_max_relaxation=constants.CONF_MED_MAX_RELAXATION,
    )


def tier_expr(thresholds: ConfThresholds) -> pl.Expr:
    """valuation._confidence as a polars expression over the records frame."""
    high = (
        (pl.col("pool_size") >= thresholds.high_min_pool)
        & (pl.col("iqr_log") <= thresholds.high_max_iqr_log)
        & (pl.col("relaxation_level") <= thresholds.high_max_relaxation)
    )
    medium = (
        (pl.col("pool_size") >= thresholds.med_min_pool)
        & (pl.col("iqr_log") <= thresholds.med_max_iqr_log)
        & (pl.col("relaxation_level") <= thresholds.med_max_relaxation)
    )
    return (
        pl.when(pl.col("insufficient"))
        .then(pl.lit("insufficient"))
        .when(high)
        .then(pl.lit("high"))
        .when(medium)
        .then(pl.lit("medium"))
        .otherwise(pl.lit("low"))
    )


def tier_stats(records: pl.DataFrame, thresholds: ConfThresholds) -> pl.DataFrame:
    """n / coverage / median width per tier under a candidate setting."""
    actual = pl.col("actual_multiplier")
    return (
        records.filter(~pl.col("insufficient"))
        .with_columns(tier=tier_expr(thresholds))
        .group_by("tier")
        .agg(
            n=pl.len(),
            coverage=((pl.col("q25") <= actual) & (actual <= pl.col("q75"))).mean(),
            width_median=(pl.col("q75").log() - pl.col("q25").log()).median(),
        )
        .sort("tier")
    )


def _is_honest(stats: dict[str, dict[str, Any]]) -> bool:
    high, medium = stats.get("high"), stats.get("medium")
    if high is None or medium is None:
        return False
    return bool(
        high["n"] >= MIN_TIER_N
        and medium["n"] >= MIN_TIER_N
        and HIGH_COVERAGE_BAND[0] <= high["coverage"] <= HIGH_COVERAGE_BAND[1]
        and MED_COVERAGE_BAND[0] <= medium["coverage"] <= MED_COVERAGE_BAND[1]
        and high["width_median"] < medium["width_median"]
    )


@dataclass(frozen=True)
class ConfProposal:
    thresholds: ConfThresholds | None  # None: nothing honest, keep the hand-set values
    stats: pl.DataFrame  # tier table of the chosen (or hand-set) setting
    n_candidates: int
    n_honest: int


def propose_conf_thresholds(records: pl.DataFrame) -> ConfProposal:
    """Among honest settings: max n(high), then coverage closest to 50%."""
    candidates = [
        ConfThresholds(*combo)
        for combo in product(
            HIGH_MIN_POOL_GRID,
            HIGH_MAX_IQR_GRID,
            HIGH_MAX_RELAX_GRID,
            MED_MIN_POOL_GRID,
            MED_MAX_IQR_GRID,
            MED_MAX_RELAX_GRID,
        )
        # High must be at least as strict as medium on every axis.
        if combo[0] >= combo[3] and combo[1] <= combo[4] and combo[2] <= combo[5]
    ]
    best: tuple[float, float, int] | None = None
    chosen: ConfThresholds | None = None
    n_honest = 0
    for index, candidate in enumerate(candidates):
        stats = {row["tier"]: row for row in tier_stats(records, candidate).iter_rows(named=True)}
        if not _is_honest(stats):
            continue
        n_honest += 1
        key = (-stats["high"]["n"], abs(stats["high"]["coverage"] - 0.5), index)
        if best is None or key < best:
            best = key
            chosen = candidate
    return ConfProposal(
        thresholds=chosen,
        stats=tier_stats(records, chosen if chosen is not None else hand_set_thresholds()),
        n_candidates=len(candidates),
        n_honest=n_honest,
    )


@dataclass(frozen=True)
class CalibrationDecision:
    needed: bool
    pooled_coverage: float
    shifts: dict[str, float]  # tier -> delta; all 0.0 when not needed
    tier_coverage: dict[str, float]  # nominal coverage per tier (diagnostic)


def _mean(series: pl.Series) -> float:
    value = series.mean()
    return float(value) if isinstance(value, int | float) else 0.0


def _tier_coverage_at_shift(rows: list[dict[str, Any]], shift: float) -> float:
    covered = 0
    for row in rows:
        lo = weighted_quantile(
            row["pool_multipliers"], row["pool_similarities"], max(0.05, 0.25 - shift)
        )
        hi = weighted_quantile(
            row["pool_multipliers"], row["pool_similarities"], min(0.95, 0.75 + shift)
        )
        covered += lo <= row["actual_multiplier"] <= hi
    return covered / len(rows)


def calibration_shifts(records: pl.DataFrame, thresholds: ConfThresholds) -> CalibrationDecision:
    """Validation-coverage decision: inside the band, no calibration; outside,
    one delta per tier minimizing |coverage - 50%|, recomputed from pools."""
    actual = pl.col("actual_multiplier")
    scored = records.filter(~pl.col("insufficient")).with_columns(
        tier=tier_expr(thresholds),
        covered=(pl.col("q25") <= actual) & (actual <= pl.col("q75")),
    )
    pooled = _mean(scored.get_column("covered"))
    by_tier = {
        str(tier): scored.filter(pl.col("tier") == tier) for tier in ("high", "medium", "low")
    }
    tier_coverage = {
        tier: _mean(frame.get_column("covered")) for tier, frame in by_tier.items() if frame.height
    }
    shifts = {"high": 0.0, "medium": 0.0, "low": 0.0}
    if CAL_TRIGGER_BAND[0] <= pooled <= CAL_TRIGGER_BAND[1]:
        return CalibrationDecision(
            needed=False, pooled_coverage=pooled, shifts=shifts, tier_coverage=tier_coverage
        )
    for tier, frame in by_tier.items():
        if frame.height < MIN_TIER_N:  # too thin to fit; stays nominal, documented
            continue
        rows = frame.select("pool_multipliers", "pool_similarities", "actual_multiplier").to_dicts()
        shifts[tier] = min(
            CAL_DELTA_GRID,
            key=lambda delta: (abs(_tier_coverage_at_shift(rows, delta) - 0.5), delta),
        )
    return CalibrationDecision(
        needed=True, pooled_coverage=pooled, shifts=shifts, tier_coverage=tier_coverage
    )


def render_thresholds_snippet(proposal: ConfProposal, decision: CalibrationDecision) -> str:
    """The CONF_*/CAL_* replacement block for the reviewed freeze commit."""
    thresholds = proposal.thresholds if proposal.thresholds is not None else hand_set_thresholds()
    kept = "" if proposal.thresholds is not None else " (hand-set kept: no honest grid setting)"
    ratio_high = math.exp(thresholds.high_max_iqr_log)
    ratio_med = math.exp(thresholds.med_max_iqr_log)
    lines = [
        f"# Set from validation tier honesty ({proposal.n_honest}/{proposal.n_candidates} "
        f"honest grid settings){kept}; calibration decided on validation coverage "
        f"{decision.pooled_coverage:.3f}.",
        f"CONF_HIGH_MIN_POOL = {thresholds.high_min_pool}",
        f"CONF_HIGH_MAX_IQR_LOG = {thresholds.high_max_iqr_log!r}"
        f"  # ~= q75/q25 multiplier ratio of {ratio_high:.2f}",
        f"CONF_HIGH_MAX_RELAXATION = {thresholds.high_max_relaxation}",
        f"CONF_MED_MIN_POOL = {thresholds.med_min_pool}",
        f"CONF_MED_MAX_IQR_LOG = {thresholds.med_max_iqr_log!r}"
        f"  # ~= q75/q25 multiplier ratio of {ratio_med:.2f}",
        f"CONF_MED_MAX_RELAXATION = {thresholds.med_max_relaxation}",
        f"CAL_SHIFT_HIGH = {decision.shifts['high']!r}",
        f"CAL_SHIFT_MEDIUM = {decision.shifts['medium']!r}",
        f"CAL_SHIFT_LOW = {decision.shifts['low']!r}",
    ]
    return "\n".join(lines) + "\n"
