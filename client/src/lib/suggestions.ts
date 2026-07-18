import type { DestinationLeague } from './types';

/**
 * Three one-click destination suggestions for the simulator's idle state.
 * Leagues arrive strength-sorted from the API, so: the strongest league the
 * player isn't already in (the ambition case), a strength neighbour of the
 * current league (the sideways case), and a mid-list league (the contrast
 * case) — topped up from the head and deduped when the list is short.
 */
export function suggestedDestinations(
  leagues: DestinationLeague[],
  currentLeagueId: string | null,
): DestinationLeague[] {
  const eligible = leagues.filter((league) => league.league_id !== currentLeagueId);
  if (eligible.length === 0) return [];

  const picks: DestinationLeague[] = [];
  const seen = new Set<string>();
  const add = (league: DestinationLeague | undefined) => {
    if (league && league.league_id !== currentLeagueId && !seen.has(league.league_id)) {
      seen.add(league.league_id);
      picks.push(league);
    }
  };

  add(eligible[0]);
  const currentIndex = leagues.findIndex((league) => league.league_id === currentLeagueId);
  if (currentIndex >= 0) add(leagues[currentIndex + 1] ?? leagues[currentIndex - 1]);
  add(eligible[Math.floor(eligible.length / 2)]);
  for (const league of eligible) {
    if (picks.length >= 3) break;
    add(league);
  }
  return picks.slice(0, 3);
}
