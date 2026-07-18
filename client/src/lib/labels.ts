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
