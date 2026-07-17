"""Range + confidence from the comp pool's weighted multiplier quantiles.

The range IS the pool: weighted quantiles of the shown comps' multipliers
applied to the player's current value - never a model output. Confidence
comes from pool size, dispersion (IQR of log multipliers) and how far the
relaxation ladder had to climb. Fewer than MIN_COMPS_FOR_RANGE usable comps
means NO range at all. Backtest calibration may widen a tier's reported
endpoints to (0.25 - shift, 0.75 + shift), but they stay order statistics
of the same pool - traceability is never traded away.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import Literal

from app.services import constants
from app.services.comps import ScoredComp
from app.services.constants import (
    CONF_HIGH_MAX_IQR_LOG,
    CONF_HIGH_MAX_RELAXATION,
    CONF_HIGH_MIN_POOL,
    CONF_MED_MAX_IQR_LOG,
    CONF_MED_MAX_RELAXATION,
    CONF_MED_MIN_POOL,
    MIN_COMPS_FOR_RANGE,
)

Confidence = Literal["high", "medium", "low", "insufficient"]


@dataclass(frozen=True)
class ValueRange:
    q25_multiplier: float
    q50_multiplier: float
    q75_multiplier: float
    q25_eur: int
    q50_eur: int
    q75_eur: int
    iqr_log: float


def weighted_quantile(values: Sequence[float], weights: Sequence[float], q: float) -> float:
    """Cumulative-weight midpoint interpolation.

    Each sorted point owns the midpoint of its weight mass
    (c_i = (cum_before_i + w_i/2) / total); Q(q) clamps outside [c_1, c_n]
    and interpolates linearly between neighbours. Exact and deterministic for
    n = 2, monotone in q, and reduces to plain midpoint quantiles under equal
    weights.
    """
    if len(values) == 0 or len(values) != len(weights):
        raise ValueError("values and weights must be non-empty and the same length")
    if any(w < 0 for w in weights):
        raise ValueError("weights must be non-negative")
    total = float(sum(weights))
    if total <= 0:
        raise ValueError("total weight must be positive")
    pairs = sorted(zip(values, weights, strict=True))
    positions: list[tuple[float, float]] = []
    cum = 0.0
    for value, weight in pairs:
        positions.append(((cum + weight / 2) / total, value))
        cum += weight
    if q <= positions[0][0]:
        return positions[0][1]
    if q >= positions[-1][0]:
        return positions[-1][1]
    for (c_lo, v_lo), (c_hi, v_hi) in pairwise(positions):
        if c_lo <= q <= c_hi:
            if c_hi == c_lo:
                return v_lo
            t = (q - c_lo) / (c_hi - c_lo)
            return v_lo + t * (v_hi - v_lo)
    return positions[-1][1]  # pragma: no cover - unreachable by construction


def _confidence(pool_size: int, iqr_log: float, relaxation_level: int) -> Confidence:
    if (
        pool_size >= CONF_HIGH_MIN_POOL
        and iqr_log <= CONF_HIGH_MAX_IQR_LOG
        and relaxation_level <= CONF_HIGH_MAX_RELAXATION
    ):
        return "high"
    if (
        pool_size >= CONF_MED_MIN_POOL
        and iqr_log <= CONF_MED_MAX_IQR_LOG
        and relaxation_level <= CONF_MED_MAX_RELAXATION
    ):
        return "medium"
    return "low"


def _calibration_shift(confidence: Confidence) -> float:
    # Module-attribute access so the tuned values apply without re-import.
    shifts = {
        "high": constants.CAL_SHIFT_HIGH,
        "medium": constants.CAL_SHIFT_MEDIUM,
        "low": constants.CAL_SHIFT_LOW,
    }
    return shifts.get(confidence, 0.0)


def summarize_pool(
    pool: Sequence[ScoredComp], current_value: int, relaxation_level: int
) -> tuple[ValueRange | None, Confidence]:
    if len(pool) < MIN_COMPS_FOR_RANGE:
        return None, "insufficient"
    multipliers = [comp.multiplier for comp in pool]
    weights = [comp.similarity for comp in pool]
    q50 = weighted_quantile(multipliers, weights, 0.50)
    logs = [math.log(m) for m in multipliers]
    # Dispersion and confidence are always judged at the nominal 25/75
    # levels; calibration must not move a pool between tiers.
    iqr_log = weighted_quantile(logs, weights, 0.75) - weighted_quantile(logs, weights, 0.25)
    confidence = _confidence(len(pool), iqr_log, relaxation_level)
    shift = _calibration_shift(confidence)
    q25 = weighted_quantile(multipliers, weights, max(0.05, 0.25 - shift))
    q75 = weighted_quantile(multipliers, weights, min(0.95, 0.75 + shift))
    value_range = ValueRange(
        q25_multiplier=q25,
        q50_multiplier=q50,
        q75_multiplier=q75,
        q25_eur=round(current_value * q25),
        q50_eur=round(current_value * q50),
        q75_eur=round(current_value * q75),
        iqr_log=iqr_log,
    )
    return value_range, confidence
