// Human labels for the API's compact codes.

const POSITION_LABELS: Record<string, string> = {
  GK: 'Goalkeeper',
  DEF: 'Defender',
  MID: 'Midfielder',
  ATT: 'Attacker',
};

export function positionLabel(code: string): string {
  return POSITION_LABELS[code] ?? code;
}

/**
 * Named league tiers (fixed ln-strength thresholds, per the README): the
 * name IS the plain meaning, so a badge never needs a tooltip to decode a
 * bare number. Unknown numbers fall back to the raw form defensively.
 */
const TIER_LABELS: Record<number, string> = {
  1: 'Elite league',
  2: 'Strong league',
  3: 'Emerging league',
  4: 'Developing league',
};

export function tierLabel(tier: number | null | undefined): string | null {
  return tier == null ? null : (TIER_LABELS[tier] ?? `Tier ${tier}`);
}

/**
 * Human wording for club_value_pct (within-league squad-value percentile,
 * 1.0 = richest) — the same continuous signal the engine's club terms use.
 */
export function clubBudgetLabel(pct: number | null | undefined): string | null {
  if (pct == null) return null;
  if (pct >= 0.85) return 'top club';
  if (pct >= 0.55) return 'upper mid-table budget';
  if (pct >= 0.25) return 'mid-table budget';
  return 'bottom-of-table budget';
}

/** Squad-value tercile within the league season: 1 = top third. */
export function tercileLabel(tercile: number | null | undefined): string | null {
  switch (tercile) {
    case 1:
      return 'Top third';
    case 2:
      return 'Mid third';
    case 3:
      return 'Bottom third';
    default:
      return null;
  }
}
