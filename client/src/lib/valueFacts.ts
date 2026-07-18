import type { ValuePoint } from './types';

/**
 * Headline facts derivable from the served valuation history alone — no
 * extra endpoint: the peak, where the current value sits against it, and
 * the 12-month change (latest point vs the newest point at least a year
 * older, mirroring the server's search-trend definition).
 */
export interface ValueFacts {
  peakValue: number;
  peakDate: string;
  /** Fraction vs the peak; 0 when the latest value IS the peak. */
  sincePeakPct: number;
  /** Fraction vs the 12-months-ago baseline; null when none that old exists. */
  delta12mPct: number | null;
}

const YEAR_MS = 365 * 24 * 60 * 60 * 1000;

export function valueFacts(history: ValuePoint[]): ValueFacts | null {
  const sorted = history
    .map((point) => ({ ...point, ts: Date.parse(point.date) }))
    .filter((point) => Number.isFinite(point.ts))
    .sort((a, b) => a.ts - b.ts);
  const latest = sorted[sorted.length - 1];
  if (!latest) return null;
  let peak = sorted[0]!;
  for (const point of sorted) {
    if (point.value_eur > peak.value_eur) peak = point; // earliest occurrence wins ties
  }
  const baseline = [...sorted].reverse().find((point) => point.ts <= latest.ts - YEAR_MS);
  return {
    peakValue: peak.value_eur,
    peakDate: peak.date,
    sincePeakPct: peak.value_eur > 0 ? latest.value_eur / peak.value_eur - 1 : 0,
    delta12mPct:
      baseline && baseline.value_eur > 0 ? latest.value_eur / baseline.value_eur - 1 : null,
  };
}
