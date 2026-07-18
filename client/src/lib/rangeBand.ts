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

function domain({ low, high, now }: RangeBandInput): { min: number; max: number } | null {
  const min = Math.min(low, now);
  const max = Math.max(high, now);
  const span = max - min;
  if (span <= 0) return null; // degenerate: every value equal
  const pad = span * PAD_FRACTION;
  return { min: min - pad, max: max + pad };
}

export function rangeBandLayout(input: RangeBandInput): RangeBandLayout {
  const d = domain(input);
  if (d === null) {
    // Degenerate: every value equal — a single centered tick.
    return { lowPct: 50, midPct: 50, highPct: 50, nowPct: 50 };
  }
  const position = (v: number) => clampPct(((v - d.min) / (d.max - d.min)) * 100);
  return {
    lowPct: position(input.low),
    midPct: position(input.mid),
    highPct: position(input.high),
    nowPct: position(input.now),
  };
}

export interface OutcomeDot {
  pct: number;
  /** True when the outcome lies beyond the band's padded domain and was
   *  pinned to the nearest edge — rendered differently so a pile-up at the
   *  edge never reads as data AT the edge. */
  clamped: boolean;
}

/**
 * Positions comp outcomes (multiplier × current value) on the SAME padded
 * domain as the band, so "the range IS these players" lines up visually.
 * The band's domain is anchored on low/high/now by design: a 4× outlier
 * must not crush the band, so outliers clamp and say so.
 */
export function outcomeDots(input: RangeBandInput, outcomes: number[]): OutcomeDot[] {
  const d = domain(input);
  return outcomes.map((value) => {
    if (d === null) return { pct: 50, clamped: value !== input.now };
    const raw = ((value - d.min) / (d.max - d.min)) * 100;
    return { pct: clampPct(raw), clamped: raw < 0 || raw > 100 };
  });
}
