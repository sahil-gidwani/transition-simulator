"""Pipeline constants: source pin, window rules, league cohorts, gate expectations.

Single source of truth shared by the pipeline and scripts/download_data.py.
Values under PINNED_EXPECTATIONS are measured on the pinned dataset revision
(see docs/data-notes.md); bumping the pin requires re-running the audit and
re-measuring them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

# --- source pin --------------------------------------------------------------

HF_REPO = "ngeorgea/transfermarkt-player-scores"
# Upstream sync of 2026-06-29; transfers.csv = 175,043 rows (healthy build).
PINNED_HF_REVISION = "7dbc5b38ba6efdc439933b00c2f4b4a7405dd681"

# --- paths -------------------------------------------------------------------

SERVER_DIR = Path(__file__).resolve().parents[1]
RAW_DIR_DEFAULT = SERVER_DIR / "data" / "raw"
PROCESSED_DIR_DEFAULT = SERVER_DIR / "data" / "processed"
MANUAL_ELO_FIXES_CSV = SERVER_DIR / "data" / "manual" / "elo_manual_fixes.csv"
REPORT_MD_DEFAULT = SERVER_DIR.parent / "docs" / "pipeline-report.md"

# --- valuation windows (see docs/data-notes.md, "Feasibility funnel") ---------

V_BEFORE_MAX_DAYS = 180  # v_before: last valuation strictly before transfer, within 180d
V_AFTER_MIN_DAYS = 180  # v_after: first valuation in [t+180d, t+540d]
V_AFTER_MAX_DAYS = 540
LOAN_MAX_RETURN_DAYS = 548  # ~18 months: A->B then B->A within this gap smells like a loan

SEASON_MIN = 2012  # transition universe starts season 2012/13
SEASON_START_MONTH = 7  # seasons run July-June; label = starting year

ELO_ASOF_TOLERANCE_DAYS = 45
SQUAD_VALUE_STALENESS_DAYS = 365  # a valuation older than this at season start is ignored

# League-season stats (median/strength/tier) and within-league terciles are
# only meaningful over a real membership. The smallest genuine covered top
# flight has 10+ clubs; every observed league-season below 8 members is a
# snapshot-era stub (RSK1 2013 had one member). Below the floor the stats are
# null and league_seasons.stats_valid flags it.
MIN_CLUBS_FOR_LEAGUE_STATS = 8

# Display tiers: fixed ln-strength thresholds, pinned like gate expectations
# and re-derived only on a data re-pin. Rank-quartile bucketing forced a
# 31-league season into 8/8/8/7 and put the largest strength gap INSIDE
# tier 1; these cuts are anchored in the latest season's natural gaps after
# the membership fix: 18.4 sits in the FR1<->BRA1 gap (~EUR 98M median
# squad value), 17.0 at the strong-second-rank boundary (~EUR 24M), 16.3 at
# the mid/tail boundary (~EUR 12M). Thresholds are nominal EUR by design -
# "no covered league had an Elite-sized median in 2012" is the honest
# statement, and the origin filter's +/-1 tier band absorbs that era drift.
# A league changes tier only after TIER_HYSTERESIS_SEASONS consecutive
# seasons across a cut, so knife-edge leagues don't flap year to year.
TIER_STRENGTH_THRESHOLDS: tuple[float, float, float] = (18.4, 17.0, 16.3)
TIER_HYSTERESIS_SEASONS = 2
MINUTES_WINDOW_DAYS = 365  # minutes_share_pre looks back this far from the transfer
PROFILE_MIN_MINUTES = 450  # percentile floor for profile stats peer groups

PSEUDO_CLUB_PATTERN = r"(?i)retired|without club|unknown|career break|ban"

POSITION_GROUPS: dict[str, str] = {
    "Goalkeeper": "GK",
    "Centre-Back": "DEF",
    "Left-Back": "DEF",
    "Right-Back": "DEF",
    "Defensive Midfield": "MID",
    "Central Midfield": "MID",
    "Attacking Midfield": "MID",
    "Left Midfield": "MID",
    "Right Midfield": "MID",
    "Left Winger": "ATT",
    "Right Winger": "ATT",
    "Second Striker": "ATT",
    "Centre-Forward": "ATT",
}
COARSE_POSITION_GROUPS: dict[str, str] = {
    "Goalkeeper": "GK",
    "Defender": "DEF",
    "Midfield": "MID",
    "Attack": "ATT",
}

# League cohorts by match-data coverage (games/appearances), from the audit:
# legacy leagues have match data from 2012; the rest only from 2024. Minutes
# and percentile features are nullable outside coverage and never gate
# comp eligibility.
LEGACY_LEAGUES: tuple[str, ...] = (
    "GB1",
    "ES1",
    "IT1",
    "L1",
    "FR1",
    "NL1",
    "PO1",
    "BE1",
    "TR1",
    "GR1",
    "SC1",
    "DK1",
    "RU1",
    "UKR1",
)
EURO_2024_LEAGUES: tuple[str, ...] = ("A1", "C1", "KR1", "NO1", "PL1", "RO1", "SE1", "SER1", "TS1")
NEW_LEAGUES: tuple[str, ...] = ("MLS1", "BRA1", "ARG1", "JAP1", "RSK1", "MEX1", "AUS1", "SA1")

# --- gate expectations ---------------------------------------------------------


@dataclass(frozen=True)
class FunnelCounts:
    """Transfer feasibility funnel; the pinned values are the audited numbers."""

    raw: int
    cleaned: int
    in_scope: int
    with_v_before: int
    observable: int
    with_v_after: int
    non_loan: int


@dataclass(frozen=True)
class Expectations:
    """Hard gate targets, measured on the pinned revision."""

    # input floors (defense in depth; the funnel gate below is exact)
    min_transfers: int
    min_valuations: int
    min_players: int
    players_columns: int
    # measured, exact: a mismatch means a different (or defective) vintage
    max_valuation_date: date
    censor_horizon: date  # max_valuation_date - V_AFTER_MIN_DAYS
    funnel: FunnelCounts
    # output floors, measured values recorded in meta.json
    min_transitions_non_loan: int
    min_player_values: int
    min_elo_touch_coverage: float
    min_minutes_nonnull_legacy: float
    max_total_bytes: int


PINNED_EXPECTATIONS = Expectations(
    min_transfers=150_000,
    min_valuations=500_000,
    min_players=30_000,
    players_columns=26,
    max_valuation_date=date(2026, 6, 12),
    censor_horizon=date(2025, 12, 14),
    funnel=FunnelCounts(
        raw=175_043,
        cleaned=174_917,
        in_scope=46_601,
        with_v_before=42_817,
        observable=39_510,
        with_v_after=38_284,
        non_loan=19_706,
    ),
    min_transitions_non_loan=19_000,
    min_player_values=600_000,  # measured: 617,351 dated valuations for in-scope players
    # Measured 0.7918 after restricting automatic Elo mapping to UEFA leagues,
    # refusing 1-token-vs-3-token fuzzy matches, and restoring the guard's 27
    # legitimate casualties (compact ClubElo names like "Napoli"/"Brighton")
    # via verified manual fixes. The pre-guard 0.8434 was inflated by false
    # positives (River Plate -> "Atletico", PSG -> "Paris FC" etc.); honest
    # coverage is lower and the floor is pinned just below it.
    min_elo_touch_coverage=0.78,
    min_minutes_nonnull_legacy=0.60,
    max_total_bytes=50 * 1024 * 1024,
)
