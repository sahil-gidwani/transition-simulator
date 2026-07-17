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

export function tierLabel(tier: number | null | undefined): string | null {
  return tier == null ? null : `Tier ${tier}`;
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
