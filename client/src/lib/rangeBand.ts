/**
 * Pure geometry for the predicted-range band: positions (as 0–100 track
 * percentages) for the low/mid/high prediction and the player's current
 * value over a padded domain. The domain always contains "now", so the
 * marker can never fall off the track even when the whole range sits below
 * or above the current value.
 */
export interface RangeBandInput {
  low: number;
  mid: number;
  high: number;
  now: number;
}

export interface RangeBandLayout {
  lowPct: number;
  midPct: number;
  highPct: number;
  nowPct: number;
}

const PAD_FRACTION = 0.08;

function clampPct(value: number): number {
  return Math.min(100, Math.max(0, value));
}

export function rangeBandLayout({ low, mid, high, now }: RangeBandInput): RangeBandLayout {
  const min = Math.min(low, now);
  const max = Math.max(high, now);
  const span = max - min;
  if (span <= 0) {
    // Degenerate: every value equal — a single centered tick.
    return { lowPct: 50, midPct: 50, highPct: 50, nowPct: 50 };
  }
  const pad = span * PAD_FRACTION;
  const domainMin = min - pad;
  const domainMax = max + pad;
  const position = (v: number) => clampPct(((v - domainMin) / (domainMax - domainMin)) * 100);
  return {
    lowPct: position(low),
    midPct: position(mid),
    highPct: position(high),
    nowPct: position(now),
  };
}
