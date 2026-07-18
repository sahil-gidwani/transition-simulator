export type Trend = 'rise' | 'decline' | 'flat';

/**
 * The one place the sign of a comp's delta becomes a semantic trend. The
 * slope chart and the delta figure on a comp card must never disagree.
 */
export function compTrend(deltaPct: number): Trend {
  if (deltaPct > 0) return 'rise';
  if (deltaPct < 0) return 'decline';
  return 'flat';
}
