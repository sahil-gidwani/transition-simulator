/**
 * Pure state helpers for the A-vs-B compare tray. A pin is a snapshot of a
 * simulation verdict (simulations are deterministic and URL-addressable, so
 * the snapshot always has a live link back to its source). At most two pins:
 * comparing is a pairwise act, and pinning a third replaces the older pin.
 */
export interface ComparePin {
  /** Identity of the simulation: player + destination. */
  key: string;
  playerName: string;
  destinationLabel: string;
  /** The simulate URL that reproduces this verdict. */
  url: string;
  lowEur: number;
  midEur: number;
  highEur: number;
  confidence: string;
}

export const MAX_PINS = 2;

export function pinKey(playerId: number, leagueId: string, clubId: number | null): string {
  return `${playerId}:${leagueId}:${clubId ?? 'any'}`;
}

export function addPin(pins: ComparePin[], pin: ComparePin): ComparePin[] {
  const without = pins.filter((existing) => existing.key !== pin.key);
  return [...without.slice(-(MAX_PINS - 1)), pin];
}

export function removePin(pins: ComparePin[], key: string): ComparePin[] {
  return pins.filter((existing) => existing.key !== key);
}

export function hasPin(pins: ComparePin[], key: string): boolean {
  return pins.some((existing) => existing.key === key);
}

/** Midpoint gap of pin B vs pin A, as a fraction; null unless both exist. */
export function midpointGap(pins: ComparePin[]): number | null {
  if (pins.length < 2) return null;
  const [a, b] = pins;
  if (!a || !b || a.midEur <= 0) return null;
  return b.midEur / a.midEur - 1;
}
