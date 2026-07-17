import { describe, expect, it } from 'vitest';
import {
  formatAge,
  formatDate,
  formatEuroCompact,
  formatRange,
  formatSeason,
  formatSignedPct,
} from './format';

describe('formatEuroCompact', () => {
  it('renders an em dash for missing values', () => {
    expect(formatEuroCompact(null)).toBe('—');
    expect(formatEuroCompact(undefined)).toBe('—');
  });

  it('renders zero and sub-thousand values plainly', () => {
    expect(formatEuroCompact(0)).toBe('€0');
    expect(formatEuroCompact(850)).toBe('€850');
  });

  it('renders thousands with a k suffix', () => {
    expect(formatEuroCompact(850_000)).toBe('€850k');
    expect(formatEuroCompact(1_500)).toBe('€2k');
  });

  it('promotes 999,999 to €1M rather than €1000k', () => {
    expect(formatEuroCompact(999_999)).toBe('€1M');
  });

  it('renders millions with one decimal, stripping .0', () => {
    expect(formatEuroCompact(38_000_000)).toBe('€38M');
    expect(formatEuroCompact(38_500_000)).toBe('€38.5M');
  });

  it('renders billions', () => {
    expect(formatEuroCompact(1_200_000_000)).toBe('€1.2B');
  });

  it('renders negative amounts with a leading minus', () => {
    expect(formatEuroCompact(-5_000_000)).toBe('−€5M');
  });
});

describe('formatSignedPct', () => {
  it('renders an em dash for missing values', () => {
    expect(formatSignedPct(null)).toBe('—');
  });

  it('renders zero unsigned, including values that round to zero', () => {
    expect(formatSignedPct(0)).toBe('0%');
    expect(formatSignedPct(0.004)).toBe('0%');
    expect(formatSignedPct(-0.004)).toBe('0%');
  });

  it('signs rises and declines', () => {
    expect(formatSignedPct(0.24)).toBe('+24%');
    expect(formatSignedPct(-0.3)).toBe('−30%');
    expect(formatSignedPct(-0.304)).toBe('−30%');
    expect(formatSignedPct(2.4)).toBe('+240%');
  });
});

describe('formatAge', () => {
  it('floors fractional ages', () => {
    expect(formatAge(24.6)).toBe('24');
    expect(formatAge(24)).toBe('24');
  });

  it('renders an em dash for missing ages', () => {
    expect(formatAge(null)).toBe('—');
  });
});

describe('formatDate', () => {
  it('renders day month year without timezone drift', () => {
    // new Date('2026-03-12') would show 11 Mar in negative-offset timezones.
    expect(formatDate('2026-03-12')).toBe('12 Mar 2026');
    expect(formatDate('2024-01-01')).toBe('1 Jan 2024');
    expect(formatDate('2025-12-31')).toBe('31 Dec 2025');
  });

  it('renders an em dash for missing dates', () => {
    expect(formatDate(null)).toBe('—');
    expect(formatDate('')).toBe('—');
  });

  it('falls back to the raw string when the shape is unexpected', () => {
    expect(formatDate('not-a-date')).toBe('not-a-date');
  });
});

describe('formatRange', () => {
  it('compresses a shared unit', () => {
    expect(formatRange(38_000_000, 46_000_000)).toBe('€38–46M');
    expect(formatRange(600_000, 850_000)).toBe('€600–850k');
  });

  it('keeps both units when they differ', () => {
    expect(formatRange(850_000, 1_200_000)).toBe('€850k–€1.2M');
  });

  it('collapses equal endpoints to a single value', () => {
    expect(formatRange(40_000_000, 40_000_000)).toBe('€40M');
  });

  it('renders an em dash when either endpoint is missing', () => {
    expect(formatRange(null, 46_000_000)).toBe('—');
    expect(formatRange(38_000_000, undefined)).toBe('—');
  });

  it('does not compress sub-thousand endpoints (no unit suffix)', () => {
    expect(formatRange(500, 900)).toBe('€500–€900');
  });
});

describe('formatSeason', () => {
  it('renders football season labels', () => {
    expect(formatSeason(2019)).toBe('2019/20');
    expect(formatSeason(2009)).toBe('2009/10');
  });

  it('pads the century rollover', () => {
    expect(formatSeason(1999)).toBe('1999/00');
  });

  it('renders an em dash for missing seasons', () => {
    expect(formatSeason(null)).toBe('—');
  });
});
