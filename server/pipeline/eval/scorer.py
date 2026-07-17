"""Numpy re-implementation of ladder walk, renormalized distance, top-K
selection and weighted quantiles - for the random search ONLY.

Term values are serving-computed (candidates.py); this module redoes just
the aggregation, mirroring find_comps + summarize_pool operation for
operation (sequential term accumulation in serving's reduce order, the
same tie-break keys, the same cumulative-weight-midpoint quantile). Parity
is pinned by synthetic tests and a runtime gate in the tune stage. Final
validation/test numbers never come from here.
"""

from __future__ import annotations

import numpy as np

from app.services.constants import MIN_COMPS_FOR_RANGE, LadderStep, RetrievalConfig
from app.services.valuation import _calibration_shift, _confidence
from pipeline.eval.candidates import CLUB_TERM_INDICES, CandidateSet


def config_weights(config: RetrievalConfig) -> np.ndarray:
    """Weights in serving term order (see comps._distance_terms)."""
    return np.array(
        [
            config.w_log_value,
            config.w_age,
            config.w_dest_strength,
            config.w_origin_strength,
            config.w_elo,
            config.w_dest_tercile,
            config.w_origin_tercile,
            config.w_minutes,
            config.w_sub_position,
            config.w_recency,
        ]
    )


def np_weighted_quantile(values: np.ndarray, weights: np.ndarray, q: float) -> float:
    """valuation.weighted_quantile, vectorized: same (value, weight) sort,
    same cumulative-weight midpoints, same clamped linear interpolation."""
    order = np.lexsort((weights, values))
    sorted_values = values[order]
    sorted_weights = weights[order]
    midpoints = (np.cumsum(sorted_weights) - sorted_weights / 2) / sorted_weights.sum()
    if q <= midpoints[0]:
        return float(sorted_values[0])
    if q >= midpoints[-1]:
        return float(sorted_values[-1])
    return float(np.interp(q, midpoints, sorted_values))


def _mask(cands: CandidateSet, step: LadderStep) -> np.ndarray:
    """One ladder step's hard filter; NaN fails every active comparison,
    matching polars null semantics."""
    lo, hi = step.value_bracket
    mask = (cands.v_before >= lo * cands.value_eur * (1 - 1e-9)) & (
        cands.v_before <= hi * cands.value_eur * (1 + 1e-9)
    )
    if cands.query_age is not None:
        mask &= (cands.age >= cands.query_age - step.age_band) & (
            cands.age <= cands.query_age + step.age_band
        )
    if step.origin_tier_band is not None and cands.origin_tier is not None:
        with np.errstate(invalid="ignore"):
            mask &= np.abs(cands.from_tier - cands.origin_tier) <= step.origin_tier_band
    return mask


def selected_pool(
    cands: CandidateSet, config: RetrievalConfig
) -> tuple[np.ndarray, np.ndarray, int]:
    """(indices into cands, similarities, relaxation level), in pool order -
    the numpy twin of find_comps' ladder walk + sort + head(pool_k)."""
    level = 0
    step = config.ladder[0]
    mask = _mask(cands, step)
    for level, step in enumerate(config.ladder):  # noqa: B007 - used after the loop
        mask = _mask(cands, step)
        if int(mask.sum()) >= config.min_pool_target:
            break
    idx = np.flatnonzero(mask)
    terms = cands.terms[idx]  # fancy indexing copies; safe to overwrite
    if step.drop_club_terms:
        terms[:, list(CLUB_TERM_INDICES)] = np.nan
    weights = config_weights(config)
    numerator = np.zeros(idx.size)
    weight_mass = np.zeros(idx.size)
    for j in range(terms.shape[1]):  # sequential order matches serving's reduce
        column = terms[:, j]
        active = ~np.isnan(column)
        numerator[active] += column[active] * weights[j]
        weight_mass[active] += weights[j]
    distance = numerator / weight_mass
    order = np.lexsort((cands.transfer_ord[idx], cands.player_id[idx], distance))
    selection = order[: config.pool_k]
    return idx[selection], np.exp(-distance[selection]), level


def score_query(cands: CandidateSet, config: RetrievalConfig) -> tuple[float, float, float] | None:
    """Predicted (q25, q50, q75) multipliers, or None on refusal - the numpy
    twin of summarize_pool's range math, including the tier-shifted endpoint
    levels, so the parity gate survives a future nonzero CAL_SHIFT freeze."""
    selection, similarities, level = selected_pool(cands, config)
    if selection.size < MIN_COMPS_FOR_RANGE:
        return None
    multipliers = cands.multiplier[selection]
    iqr_log = np_weighted_quantile(np.log(multipliers), similarities, 0.75) - np_weighted_quantile(
        np.log(multipliers), similarities, 0.25
    )
    shift = _calibration_shift(_confidence(int(selection.size), iqr_log, level))
    return (
        np_weighted_quantile(multipliers, similarities, max(0.05, 0.25 - shift)),
        np_weighted_quantile(multipliers, similarities, 0.50),
        np_weighted_quantile(multipliers, similarities, min(0.95, 0.75 + shift)),
    )
