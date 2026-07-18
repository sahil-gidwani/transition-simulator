import { describe, expect, it } from 'vitest';
import { rangeBandLayout } from './rangeBand';

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
