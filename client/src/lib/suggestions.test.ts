import { describe, expect, it } from 'vitest';
import type { DestinationLeague } from './types';
import { suggestedDestinations } from './suggestions';

function league(id: string): DestinationLeague {
  return {
    league_id: id,
    name: id,
    country: null,
    tier: 1,
    strength: null,
    median_squad_value_eur: null,
    clubs: [],
  };
}

// Strength-sorted, as the API serves them.
const LEAGUES = ['GB1', 'IT1', 'ES1', 'FR1', 'NL1', 'DK1', 'SC1'].map(league);

describe('suggestedDestinations', () => {
  it('never suggests the player’s own league and offers three distinct picks', () => {
    const picks = suggestedDestinations(LEAGUES, 'GB1');
    expect(picks).toHaveLength(3);
    expect(picks.map((p) => p.league_id)).not.toContain('GB1');
    expect(new Set(picks.map((p) => p.league_id)).size).toBe(3);
  });

  it('leads with the strongest available league and includes a strength neighbour', () => {
    const picks = suggestedDestinations(LEAGUES, 'ES1').map((p) => p.league_id);
    expect(picks[0]).toBe('GB1'); // strongest ≠ current
    expect(picks).toContain('FR1'); // the league just below ES1
  });

  it('suggests for players from uncovered leagues too', () => {
    const picks = suggestedDestinations(LEAGUES, null);
    expect(picks).toHaveLength(3);
    expect(picks[0]!.league_id).toBe('GB1');
  });

  it('tops up and dedupes when the list is short', () => {
    const picks = suggestedDestinations(['GB1', 'IT1'].map(league), 'GB1');
    expect(picks.map((p) => p.league_id)).toEqual(['IT1']);
  });

  it('returns nothing when the only league is the player’s own', () => {
    expect(suggestedDestinations([league('GB1')], 'GB1')).toEqual([]);
  });
});
