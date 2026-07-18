import { describe, expect, it } from 'vitest';
import { valueFacts } from './valueFacts';

const point = (date: string, value_eur: number) => ({ date, value_eur });

describe('valueFacts', () => {
  it('returns null for an empty or unparseable history', () => {
    expect(valueFacts([])).toBeNull();
    expect(valueFacts([point('garbage', 5)])).toBeNull();
  });

  it('finds the peak and the drop since it', () => {
    const facts = valueFacts([
      point('2022-01-01', 40_000_000),
      point('2023-06-01', 80_000_000),
      point('2025-06-01', 60_000_000),
    ]);
    expect(facts).not.toBeNull();
    expect(facts!.peakValue).toBe(80_000_000);
    expect(facts!.peakDate).toBe('2023-06-01');
    expect(facts!.sincePeakPct).toBeCloseTo(-0.25, 10);
  });

  it('reports zero since-peak when the latest value is the peak', () => {
    const facts = valueFacts([point('2024-01-01', 10), point('2025-01-01', 20)]);
    expect(facts!.sincePeakPct).toBe(0);
  });

  it('uses the newest point at least 12 months old as the trend baseline', () => {
    const facts = valueFacts([
      point('2023-01-01', 10_000_000), // older than needed: must NOT be the baseline
      point('2024-05-01', 20_000_000), // 13 months before latest: the baseline
      point('2025-01-01', 25_000_000), // too recent
      point('2025-06-01', 30_000_000),
    ]);
    expect(facts!.delta12mPct).toBeCloseTo(0.5, 10);
  });

  it('returns a null trend when nothing is 12 months old', () => {
    const facts = valueFacts([point('2025-05-01', 10), point('2025-06-01', 12)]);
    expect(facts!.delta12mPct).toBeNull();
  });
});
