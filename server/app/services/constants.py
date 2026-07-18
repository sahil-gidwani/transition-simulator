"""Serving-side tunables in one place.

PROVENANCE: tuned by the temporal backtest (pipeline/eval), 2026-07-18,
for ENGINE V2 (strength-band destination filter + continuous club-value
terms) on the hardened artifacts (games-authoritative membership,
UEFA-only Elo mapping, minimum-club floor). Retrieval weights, ladder
geometry incl. the destination strength bands, MIN_POOL_TARGET and POOL_K
come from a random search (300 configs, seed 20260718) scored on
validation seasons 2020-2021 (mean log pinball with date-exact comp
availability; refusals imputed at the naive-baseline pinball). Winning
config hash: 7309dc25f471 (validation pinball 0.17000 vs 0.17471 for the
hand-set priors). Confidence thresholds and calibration shifts are set
from validation tier coverage. Test seasons 2022-2024 were scored exactly
once, after this freeze. Reproduce: `uv run python -m pipeline.eval tune`
/ `thresholds`; full results in docs/eval-report.md.
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

LADDER: tuple[LadderStep, ...] = (
    LadderStep("base filters", 4.0, (0.5, 3.0), 1, dest_strength_band=0.5),
    LadderStep("age band widened to +/-4.5 years", 4.5, (0.5, 3.0), 1, dest_strength_band=0.5),
    LadderStep("value bracket widened to 0.2-5x", 4.5, (0.2, 5.0), 1, dest_strength_band=0.5),
    LadderStep("origin league tier widened to +/-2", 4.5, (0.2, 5.0), 2, dest_strength_band=0.5),
    LadderStep(
        "destination league band widened to +/-0.9 (~2.5x squad value)",
        4.5,
        (0.2, 5.0),
        2,
        dest_strength_band=0.9,
    ),
    LadderStep(
        "destination league band widened to +/-1 (~2.7x squad value); "
        "origin league filter dropped; club-level terms ignored",
        4.5,
        (0.2, 5.0),
        None,
        dest_strength_band=1.0,
        drop_club_terms=True,
    ),
)

# --- comps: distance weights + scales (term distances are dimensionless ~[0,1]) --

W_LOG_VALUE = 0.21148543746680198  # |ln v_before - ln value| / LN_VALUE_SCALE
W_AGE = 0.05238035768051688  # |age gap| / AGE_SCALE
W_DEST_STRENGTH = 0.09276095989808877  # |strength(to_league @ comp season) - strength(dest)|
W_ORIGIN_STRENGTH = 0.17218271639050992  # same, origin side
W_ELO = 1.4349320732627806  # |comp to_elo_pct - dest club elo_pct| (both already 0-1)
W_DEST_CLUB_VALUE = 0.9248844395605903  # |comp to_club_value_pct - dest club pct| (both 0-1)
W_ORIGIN_CLUB_VALUE = 0.18064931146326058  # |comp from_club_value_pct - query club pct|
W_MINUTES = 0.06966926598002375  # |minutes_share_pre - query minutes_share| (both 0-1)
W_SUB_POSITION = 0.2962751466253388  # 0 if same sub-position else 1
W_RECENCY = 0.3182376133078169  # (latest season - comp season) / RECENCY_SCALE

LN_VALUE_SCALE = math.log(2.5)  # the base bracket edge maps to distance 1.0
AGE_SCALE = 3.0
STRENGTH_SCALE = 1.0  # strength is ln(median squad value); 1.0 = one e-fold
RECENCY_SCALE = 13.0  # seasons spanned by the transition universe

POOL_K = 41  # comps entering the quantile pool; the API returns all of them
SHOWN_COMPS_DEFAULT = 6  # UI default: closest shown, rest expandable

# Within-league standing gap (club_value_pct units) under which a comp counts
# as evidence ABOUT the selected club's standing: drives the "similar standing
# in league" tag and pool_quality.club_standing_support. A pool with zero
# support means the club term is extrapolating - the caveats say so.
CLUB_STANDING_ALIKE = 0.15


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
# levels. PROVENANCE: the engine-v2 validation-coverage decision kept
# calibration OFF (pooled coverage 51.6%, inside the 45-55 trigger band)
# and kept the hand-set confidence thresholds (0/324 honest grid settings)
# - see docs/eval-report.md. A future retune re-decides these.
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
# A selected club is "indistinct" when its midpoint sits within this of the
# league-only answer: the precedent cannot distinguish destinations that
# fine, and the response says so rather than dressing up noise as club-level
# insight (principles 3-4). Judged on midpoint drift alone - pool identity
# deliberately does NOT matter, because above POOL_K candidates the club
# terms reshuffle which comps make the cap even when the answer is unmoved.
CLUB_INDISTINCT_MAX_MID_DRIFT = 0.02
SMALL_POOL_MAX = 5  # pools this small get an explicit caveat
DECLINER_CAVEAT_MIN_SHARE = 0.2  # decliner share that triggers "X of Y lost value"
STALE_VALUE_DAYS = 365  # valuations older than this get a staleness note
NAMED_PRECEDENTS = 3  # closest precedents called out by name
