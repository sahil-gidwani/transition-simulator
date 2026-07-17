import { ApiError } from './api';
import type { Prediction, SimulationResponse } from './types';

export type SimulatorState =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'no_valuation'; message: string }
  | { kind: 'error'; message: string }
  | { kind: 'insufficient'; result: SimulationResponse }
  | { kind: 'result'; result: SimulationResponse; prediction: Prediction };

export interface SimulatorInputs {
  destinationSelected: boolean;
  isPending: boolean;
  error: unknown;
  data: SimulationResponse | undefined;
}

/**
 * Collapses the destination selection + simulation query into one renderable state.
 * Order matters: a disabled query still reports `isPending: true`, so the idle check
 * must run before the loading check.
 */
export function deriveSimulatorState({
  destinationSelected,
  isPending,
  error,
  data,
}: SimulatorInputs): SimulatorState {
  if (!destinationSelected) return { kind: 'idle' };
  if (error instanceof ApiError && error.code === 'player_without_value') {
    return { kind: 'no_valuation', message: error.message };
  }
  if (error != null) {
    return {
      kind: 'error',
      message: error instanceof Error ? error.message : 'Something went wrong',
    };
  }
  if (isPending || data === undefined) return { kind: 'loading' };
  if (data.prediction === null) return { kind: 'insufficient', result: data };
  return { kind: 'result', result: data, prediction: data.prediction };
}
