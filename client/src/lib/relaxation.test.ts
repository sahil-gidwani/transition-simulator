import { describe, expect, it } from 'vitest';
import { humanizeRelaxationStep } from './relaxation';

describe('humanizeRelaxationStep', () => {
  it('rewrites the age-band step', () => {
    expect(humanizeRelaxationStep('age band widened to +/-6 years')).toBe(
      'included players up to 6 years older or younger',
    );
  });

  it('rewrites the value-bracket step, decimals included', () => {
    expect(humanizeRelaxationStep('value bracket widened to 0.25-4x')).toBe(
      "included players valued from 0.25× to 4× this player's value",
    );
  });

  it('rewrites the origin-tier step', () => {
    expect(humanizeRelaxationStep('origin league tier widened to +/-2')).toBe(
      'included moves from leagues up to 2 strength tiers apart',
    );
  });

  it('rewrites the dropped-filter step', () => {
    expect(humanizeRelaxationStep('origin league filter dropped; club-level terms ignored')).toBe(
      'considered moves from any league, setting club-level detail aside',
    );
  });

  it('captures retuned numbers instead of hardcoding them', () => {
    expect(humanizeRelaxationStep('age band widened to +/-4 years')).toBe(
      'included players up to 4 years older or younger',
    );
    expect(humanizeRelaxationStep('value bracket widened to 0.5-2x')).toBe(
      "included players valued from 0.5× to 2× this player's value",
    );
  });

  it('passes unknown steps through verbatim — widening is never hidden', () => {
    expect(humanizeRelaxationStep('minutes filter loosened to 10%')).toBe(
      'minutes filter loosened to 10%',
    );
    expect(humanizeRelaxationStep('')).toBe('');
  });
});
