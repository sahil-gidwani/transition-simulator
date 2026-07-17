"""Serving-side tunables in one place.

PROVENANCE: tuned by the temporal backtest (pipeline/eval), 2026-07-18.
Retrieval weights, ladder geometry, MIN_POOL_TARGET and POOL_K come from a
random search (300 configs, seed 20260718) scored on validation seasons
2020-2021 (mean log pinball with date-exact comp availability; refusals
imputed at the naive-baseline pinball). Winning config hash: ff9f546e0b3c.
Confidence thresholds and calibration shifts are set from validation tier
coverage. Test seasons 2022-2024 were scored exactly once, after this
freeze. Reproduce: `uv run python -m pipeline.eval tune` / `thresholds`;
full results in docs/eval-report.md.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# --- search -------------------------------------------------------------------

SEARCH_MIN_QUERY_CHARS = 2  # shorter normalized queries return no results
SEARCH_LIMIT = 20

# --- comps: hard filters + relaxation ladder ------------------------------------


@dataclass(frozen=True)
class LadderStep:
    """One relaxation level; steps are cumulative widenings of the base filters."""

    label: str
    age_band: float  # comp age_at_transfer within query age +/- this
    value_bracket: tuple[float, float]  # comp v_before / query value within this
    origin_tier_band: int | None  # |comp from_tier - origin tier| <= this; None = dropped
    drop_club_terms: bool = False  # tercile/Elo ranking terms ignored at this level


MIN_POOL_TARGET = 6  # fewer matches than this fires the next ladder step

LADDER: tuple[LadderStep, ...] = (
    LadderStep("base filters", 2.5, (0.4, 2.5), 1),
    LadderStep("age band widened to +/-6 years", 6.0, (0.4, 2.5), 1),
    LadderStep("value bracket widened to 0.25-4x", 6.0, (0.25, 4.0), 1),
    LadderStep("origin league tier widened to +/-2", 6.0, (0.25, 4.0), 2),
    LadderStep(
        "origin league filter dropped; club-level terms ignored",
        6.0,
        (0.25, 4.0),
        None,
        drop_club_terms=True,
    ),
)

# --- comps: distance weights + scales (term distances are dimensionless ~[0,1]) --

W_LOG_VALUE = 0.9615798626236497  # |ln v_before - ln value| / LN_VALUE_SCALE
W_AGE = 1.7274521852541642  # |age gap| / AGE_SCALE
W_DEST_STRENGTH = 0.38737463961975205  # |strength(to_league @ comp season) - strength(dest)|
W_ORIGIN_STRENGTH = 0.10142150098847284  # same, origin side
W_ELO = 0.10616890856313303  # |comp to_elo_pct - dest club elo_pct| (both already 0-1)
W_DEST_TERCILE = 1.4788477826248005  # |comp to_tercile - dest club tercile| / TERCILE_SCALE
W_ORIGIN_TERCILE = 0.4703210853041415  # |comp from_tercile - query club tercile| / TERCILE_SCALE
W_MINUTES = 0.1493551745451686  # |minutes_share_pre - query minutes_share| (both 0-1)
W_SUB_POSITION = 0.06953038612616529  # 0 if same sub-position else 1
W_RECENCY = 0.11727581685642348  # (latest season - comp season) / RECENCY_SCALE

LN_VALUE_SCALE = math.log(2.5)  # the base bracket edge maps to distance 1.0
AGE_SCALE = 3.0
STRENGTH_SCALE = 1.0  # strength is ln(median squad value); 1.0 = one e-fold
TERCILE_SCALE = 2.0
RECENCY_SCALE = 13.0  # seasons spanned by the transition universe

POOL_K = 47  # comps entering the quantile pool; the API returns all of them
SHOWN_COMPS_DEFAULT = 6  # UI default: closest shown, rest expandable


@dataclass(frozen=True)
class RetrievalConfig:
    """The comps engine's tunable surface, threaded through find_comps.

    Serving always passes DEFAULT_RETRIEVAL (assembled from the constants in
    this module); the offline backtest scores candidate configs through the
    exact same code path. Scales are not part of the config - each is
    redundant with its weight (w/scale is one effective coefficient).
    """

    w_log_value: float
    w_age: float
    w_dest_strength: float
    w_origin_strength: float
    w_elo: float
    w_dest_tercile: float
    w_origin_tercile: float
    w_minutes: float
    w_sub_position: float
    w_recency: float
    ladder: tuple[LadderStep, ...]
    min_pool_target: int
    pool_k: int


DEFAULT_RETRIEVAL = RetrievalConfig(
    w_log_value=W_LOG_VALUE,
    w_age=W_AGE,
    w_dest_strength=W_DEST_STRENGTH,
    w_origin_strength=W_ORIGIN_STRENGTH,
    w_elo=W_ELO,
    w_dest_tercile=W_DEST_TERCILE,
    w_origin_tercile=W_ORIGIN_TERCILE,
    w_minutes=W_MINUTES,
    w_sub_position=W_SUB_POSITION,
    w_recency=W_RECENCY,
    ladder=LADDER,
    min_pool_target=MIN_POOL_TARGET,
    pool_k=POOL_K,
)

# --- valuation: range + confidence ----------------------------------------------

MIN_COMPS_FOR_RANGE = 2  # below this: insufficient precedent, NO range (principle 4)

# Per-tier calibration: reported endpoints move to quantile levels
# (0.25 - shift, 0.75 + shift) of the SAME comp pool, so they remain order
# statistics of the shown comps; confidence is always judged at the nominal
# levels. PROVENANCE: 0.0 (uncalibrated) until the P5 validation-coverage
# decision overwrites them - see docs/eval-report.md.
CAL_SHIFT_HIGH = 0.0
CAL_SHIFT_MEDIUM = 0.0
CAL_SHIFT_LOW = 0.0

CONF_HIGH_MIN_POOL = 12
CONF_HIGH_MAX_IQR_LOG = 0.35  # ~= q75/q25 multiplier ratio of 1.42
CONF_HIGH_MAX_RELAXATION = 0
CONF_MED_MIN_POOL = 6
CONF_MED_MAX_IQR_LOG = 0.60  # ~= q75/q25 multiplier ratio of 1.82
CONF_MED_MAX_RELAXATION = 2

# --- narrative -------------------------------------------------------------------

DIRECTION_UP = 1.05  # q50 multiplier at/above this reads as a rise
DIRECTION_DOWN = 0.95  # at/below this reads as a decline
SMALL_POOL_MAX = 5  # pools this small get an explicit caveat
DECLINER_CAVEAT_MIN_SHARE = 0.2  # decliner share that triggers "X of Y lost value"
STALE_VALUE_DAYS = 365  # valuations older than this get a staleness note
NAMED_PRECEDENTS = 3  # closest precedents called out by name
