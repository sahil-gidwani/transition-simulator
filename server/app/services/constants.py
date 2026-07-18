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

ENGINE V2 INTERIM NOTE: the strength-band destination filter and the
continuous club-value terms carry HAND-SET priors (marked below); the v1
provenance above applies to the surviving v1 parameters only until the v2
retune re-freezes this block.
"""

from __future__ import annotations

import math
from dataclasses import KW_ONLY, dataclass

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
    _: KW_ONLY
    # |comp to_strength - destination strength| <= this (ln squad-value units;
    # 0.35 ~ 1.4x, 0.7 ~ 2x, 1.2 ~ 3.3x). The destination is the question the
    # user asked, so it is the LAST thing the ladder widens and is never
    # dropped: a comp with no destination strength is never eligible.
    dest_strength_band: float
    drop_club_terms: bool = False  # club-value/Elo ranking terms ignored at this level


MIN_POOL_TARGET = 6  # fewer matches than this fires the next ladder step

# ENGINE V2 HAND-SET PRIORS: the strength bands and the club-value weights
# below are initial values (club-value weights inherit the old tercile
# weights); the pending retune re-freezes this whole block.
LADDER: tuple[LadderStep, ...] = (
    LadderStep("base filters", 2.5, (0.4, 2.5), 1, dest_strength_band=0.35),
    LadderStep("age band widened to +/-6 years", 6.0, (0.4, 2.5), 1, dest_strength_band=0.35),
    LadderStep("value bracket widened to 0.25-4x", 6.0, (0.25, 4.0), 1, dest_strength_band=0.35),
    LadderStep("origin league tier widened to +/-2", 6.0, (0.25, 4.0), 2, dest_strength_band=0.35),
    LadderStep(
        "destination league band widened to +/-0.7 (~2.0x squad value)",
        6.0,
        (0.25, 4.0),
        2,
        dest_strength_band=0.7,
    ),
    LadderStep(
        "destination league band widened to +/-1.2 (~3.3x squad value); "
        "origin league filter dropped; club-level terms ignored",
        6.0,
        (0.25, 4.0),
        None,
        dest_strength_band=1.2,
        drop_club_terms=True,
    ),
)

# --- comps: distance weights + scales (term distances are dimensionless ~[0,1]) --

W_LOG_VALUE = 0.9615798626236497  # |ln v_before - ln value| / LN_VALUE_SCALE
W_AGE = 1.7274521852541642  # |age gap| / AGE_SCALE
W_DEST_STRENGTH = 0.38737463961975205  # |strength(to_league @ comp season) - strength(dest)|
W_ORIGIN_STRENGTH = 0.10142150098847284  # same, origin side
W_ELO = 0.10616890856313303  # |comp to_elo_pct - dest club elo_pct| (both already 0-1)
# HAND-SET PRIORS (inherit the old tercile weights) pending the v2 retune:
W_DEST_CLUB_VALUE = 1.4788477826248005  # |comp to_club_value_pct - dest club pct| (both 0-1)
W_ORIGIN_CLUB_VALUE = 0.4703210853041415  # |comp from_club_value_pct - query club pct|
W_MINUTES = 0.1493551745451686  # |minutes_share_pre - query minutes_share| (both 0-1)
W_SUB_POSITION = 0.06953038612616529  # 0 if same sub-position else 1
W_RECENCY = 0.11727581685642348  # (latest season - comp season) / RECENCY_SCALE

LN_VALUE_SCALE = math.log(2.5)  # the base bracket edge maps to distance 1.0
AGE_SCALE = 3.0
STRENGTH_SCALE = 1.0  # strength is ln(median squad value); 1.0 = one e-fold
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
    w_dest_club_value: float
    w_origin_club_value: float
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
    w_dest_club_value=W_DEST_CLUB_VALUE,
    w_origin_club_value=W_ORIGIN_CLUB_VALUE,
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
# levels. PROVENANCE: the validation-coverage decision kept calibration OFF
# (pooled coverage 53.2%, inside the 45-55 trigger band) - see
# docs/eval-report.md. A future retune re-decides these.
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
