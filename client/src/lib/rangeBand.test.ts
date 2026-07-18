import { describe, expect, it } from 'vitest';
import { outcomeDots, rangeBandLayout } from './rangeBand';

describe('rangeBandLayout', () => {
  it('orders low ≤ mid ≤ high and keeps everything inside the track', () => {
    const l = rangeBandLayout({
      low: 16_200_000,
      mid: 18_900_000,
      high: 21_700_000,
      now: 22_000_000,
    });
    expect(l.lowPct).toBeLessThan(l.midPct);
    expect(l.midPct).toBeLessThan(l.highPct);
    for (const v of Object.values(l)) {
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThanOrEqual(100);
    }
  });

  it('pads the domain so endpoints never sit on the track edges', () => {
    const l = rangeBandLayout({ low: 10, mid: 15, high: 20, now: 20 });
    expect(l.lowPct).toBeGreaterThan(0);
    expect(l.highPct).toBeLessThan(100);
  });

  it('extends the domain when now falls outside the predicted range', () => {
    const below = rangeBandLayout({ low: 30, mid: 35, high: 40, now: 10 });
    expect(below.nowPct).toBeLessThan(below.lowPct);
    const above = rangeBandLayout({ low: 30, mid: 35, high: 40, now: 90 });
    expect(above.nowPct).toBeGreaterThan(above.highPct);
  });

  it('collapses to a centered tick when all values are equal', () => {
    expect(rangeBandLayout({ low: 5, mid: 5, high: 5, now: 5 })).toEqual({
      lowPct: 50,
      midPct: 50,
      highPct: 50,
      nowPct: 50,
    });
  });

  it('positions now between low and high when it falls inside the range', () => {
    const l = rangeBandLayout({ low: 10, mid: 20, high: 30, now: 20 });
    expect(l.nowPct).toBe(l.midPct);
  });
});

describe('outcomeDots', () => {
  const input = { low: 100, mid: 150, high: 200, now: 100 };
  // domain: span 100, pad 8 -> [92, 208]

  it('positions in-domain outcomes on the same padded domain as the band', () => {
    const [dot] = outcomeDots(input, [150]);
    expect(dot.pct).toBeCloseTo(50, 5);
    expect(dot.clamped).toBe(false);
  });

  it('pins outliers to the edge and marks them clamped', () => {
    const [lowOut, highOut] = outcomeDots(input, [10, 400]);
    expect(lowOut).toEqual({ pct: 0, clamped: true });
    expect(highOut).toEqual({ pct: 100, clamped: true });
  });

  it('treats domain-edge values as in scale', () => {
    const [atMin, atMax] = outcomeDots(input, [92, 208]);
    expect(atMin).toEqual({ pct: 0, clamped: false });
    expect(atMax).toEqual({ pct: 100, clamped: false });
  });

  it('centers everything on a degenerate domain', () => {
    const flat = { low: 100, mid: 100, high: 100, now: 100 };
    expect(outcomeDots(flat, [100])).toEqual([{ pct: 50, clamped: false }]);
    expect(outcomeDots(flat, [130])).toEqual([{ pct: 50, clamped: true }]);
  });
});
