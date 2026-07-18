import { describe, expect, it } from 'vitest';
import { ApiError } from './api';
import { deriveSimulatorState } from './simulatorState';
import type { CompCard, Prediction, SimulationResponse } from './types';

const prediction: Prediction = {
  low_eur: 9_500_000,
  mid_eur: 11_000_000,
  high_eur: 13_000_000,
  low_multiplier: 0.95,
  mid_multiplier: 1.1,
  high_multiplier: 1.3,
  horizon_months: 12,
};

const comp: CompCard = {
  player_id: 100,
  player_name: 'Riser One',
  season: 2023,
  transfer_date: '2023-07-01',
  age_at_transfer: 26.4,
  from_club: 'Old Club',
  to_club: 'New Club',
  from_league: 'AA1',
  to_league: 'BB1',
  v_before_eur: 9_000_000,
  v_after_eur: 12_600_000,
  multiplier: 1.4,
  delta_pct: 0.4,
  similarity: 0.83,
  tags: ['similar market value'],
};

function simulationResponse(overrides: Partial<SimulationResponse> = {}): SimulationResponse {
  return {
    player: {
      player_id: 1,
      name: 'Sim Target',
      position_group: 'ATT',
      sub_position: 'Centre-Forward',
      age: 27,
      market_value_eur: 10_000_000,
      market_value_asof: '2026-06-01',
    },
    destination: {
      league_id: 'BB1',
      league_name: 'Beta League',
      country: 'Betaland',
      tier: 1,
      club_id: null,
      club_name: null,
      club_tercile: null,
    },
    prediction,
    direction: 'rise',
    confidence: 'medium',
    insufficient_precedent: false,
    comps: [comp],
    shown_comps: 6,
    pool_quality: {
      pool_size: 1,
      relaxation_level: 0,
      relaxation_steps: [],
      expanded_search: false,
      club_selected: false,
      elo_pool_coverage: 0,
      dest_elo_available: false,
      missing_age: false,
      missing_minutes: false,
      origin_tier_unknown: false,
      club_indistinct: false,
    },
    narrative: 'The precedent points up.',
    ...overrides,
  };
}

const base = { destinationSelected: true, isPending: false, error: null, data: undefined };

describe('deriveSimulatorState', () => {
  it('is idle when no destination is selected, even while the disabled query reports pending', () => {
    expect(deriveSimulatorState({ ...base, destinationSelected: false, isPending: true })).toEqual({
      kind: 'idle',
    });
  });

  it('is loading while the query is pending', () => {
    expect(deriveSimulatorState({ ...base, isPending: true })).toEqual({ kind: 'loading' });
  });

  it('maps the 409 player_without_value ApiError to no_valuation', () => {
    const error = new ApiError(409, 'player_without_value', 'No valuation on record');
    expect(deriveSimulatorState({ ...base, error })).toEqual({
      kind: 'no_valuation',
      message: 'No valuation on record',
    });
  });

  it('maps other ApiErrors to error', () => {
    const error = new ApiError(404, 'destination_not_found', "No destination league 'XX9'");
    expect(deriveSimulatorState({ ...base, error })).toEqual({
      kind: 'error',
      message: "No destination league 'XX9'",
    });
  });

  it('maps non-Error throwables to a generic error message', () => {
    expect(deriveSimulatorState({ ...base, error: 'boom' })).toEqual({
      kind: 'error',
      message: 'Something went wrong',
    });
  });

  it('is insufficient when prediction is null, even with an evidence comp present', () => {
    const data = simulationResponse({
      prediction: null,
      confidence: 'insufficient',
      insufficient_precedent: true,
    });
    const state = deriveSimulatorState({ ...base, data });
    expect(state.kind).toBe('insufficient');
    if (state.kind === 'insufficient') {
      expect(state.result.comps).toHaveLength(1);
    }
  });

  it('narrows the prediction out of the result state', () => {
    const data = simulationResponse();
    const state = deriveSimulatorState({ ...base, data });
    expect(state.kind).toBe('result');
    if (state.kind === 'result') {
      expect(state.prediction.mid_eur).toBe(11_000_000);
      expect(state.result.narrative).toBe('The precedent points up.');
    }
  });
});
