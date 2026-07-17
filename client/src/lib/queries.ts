import { keepPreviousData, useQuery } from '@tanstack/react-query';
import {
  getDestinations,
  getHealth,
  getPlayer,
  getPlayerPercentiles,
  postSimulation,
  searchPlayers,
} from './api';
import type { DestinationSpec } from './types';

export const queryKeys = {
  health: ['health'] as const,
  search: (q: string) => ['players', 'search', q] as const,
  player: (id: number) => ['players', id] as const,
  percentiles: (id: number) => ['players', id, 'percentiles'] as const,
  destinations: ['destinations'] as const,
  simulation: (playerId: number, leagueId: string, clubId: number | null) =>
    ['simulations', playerId, leagueId, clubId] as const,
};

export function useHealth() {
  return useQuery({ queryKey: queryKeys.health, queryFn: getHealth });
}

export function usePlayerSearch(q: string) {
  const trimmed = q.trim();
  return useQuery({
    queryKey: queryKeys.search(trimmed),
    queryFn: () => searchPlayers(trimmed),
    enabled: trimmed.length >= 2,
    placeholderData: keepPreviousData,
  });
}

export function usePlayer(id: number) {
  return useQuery({
    queryKey: queryKeys.player(id),
    queryFn: () => getPlayer(id),
    enabled: Number.isInteger(id),
  });
}

export function usePercentiles(id: number) {
  return useQuery({
    queryKey: queryKeys.percentiles(id),
    queryFn: () => getPlayerPercentiles(id),
    enabled: Number.isInteger(id),
  });
}

export function useDestinations() {
  return useQuery({ queryKey: queryKeys.destinations, queryFn: getDestinations });
}

/**
 * POST /api/simulations is a deterministic, side-effect-free read, so it is modelled
 * as a query (not a mutation): `enabled` maps onto the simulator's idle state, and
 * revisiting a destination serves the cached verdict instantly.
 */
export function useSimulation(playerId: number, destination: DestinationSpec | null) {
  return useQuery({
    queryKey:
      destination === null
        ? (['simulations', playerId, 'idle'] as const)
        : queryKeys.simulation(playerId, destination.league_id, destination.club_id ?? null),
    queryFn: () => {
      if (destination === null) {
        throw new Error('simulation query runs only with a destination selected');
      }
      return postSimulation({ player_id: playerId, destination });
    },
    enabled: destination !== null && Number.isInteger(playerId),
  });
}
