import { describe, expect, it } from 'vitest';
import { addPin, hasPin, midpointGap, pinKey, removePin, type ComparePin } from './comparePins';

function pin(key: string, midEur = 10_000_000): ComparePin {
  return {
    key,
    playerName: 'P',
    destinationLabel: 'D',
    url: `/players/1/simulate?league=${key}`,
    lowEur: midEur * 0.8,
    midEur,
    highEur: midEur * 1.2,
    confidence: 'medium',
  };
}

describe('comparePins', () => {
  it('builds a stable identity from player + destination', () => {
    expect(pinKey(7, 'GB1', null)).toBe('7:GB1:any');
    expect(pinKey(7, 'ES1', 418)).toBe('7:ES1:418');
  });

  it('caps at two pins, dropping the oldest', () => {
    let pins: ComparePin[] = [];
    pins = addPin(pins, pin('a'));
    pins = addPin(pins, pin('b'));
    pins = addPin(pins, pin('c'));
    expect(pins.map((p) => p.key)).toEqual(['b', 'c']);
  });

  it('re-pinning the same scenario refreshes it without duplication', () => {
    let pins = [pin('a', 10_000_000), pin('b')];
    pins = addPin(pins, pin('a', 12_000_000));
    expect(pins.map((p) => p.key)).toEqual(['b', 'a']);
    expect(pins[1]!.midEur).toBe(12_000_000);
  });

  it('removes by key and answers membership', () => {
    const pins = [pin('a'), pin('b')];
    expect(hasPin(pins, 'a')).toBe(true);
    expect(removePin(pins, 'a').map((p) => p.key)).toEqual(['b']);
    expect(hasPin(removePin(pins, 'a'), 'a')).toBe(false);
  });

  it('reports the midpoint gap only for a full pair', () => {
    expect(midpointGap([pin('a')])).toBeNull();
    expect(midpointGap([pin('a', 10_000_000), pin('b', 11_500_000)])).toBeCloseTo(0.15, 10);
  });
});
