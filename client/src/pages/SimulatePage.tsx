import { Link, useParams, useSearchParams } from 'react-router';
import CompsPanel from '../components/simulate/CompsPanel';
import DestinationPicker from '../components/simulate/DestinationPicker';
import InsufficientPanel from '../components/simulate/InsufficientPanel';
import NarrativeStrip from '../components/simulate/NarrativeStrip';
import NoValuationPanel from '../components/simulate/NoValuationPanel';
import PoolQualityBanner from '../components/simulate/PoolQualityBanner';
import VerdictPanel from '../components/simulate/VerdictPanel';
import EmptyState from '../components/ui/EmptyState';
import SkeletonBlock from '../components/ui/SkeletonBlock';
import { ApiError } from '../lib/api';
import { useDestinations, usePlayer, useSimulation } from '../lib/queries';
import { deriveSimulatorState } from '../lib/simulatorState';
import type { DestinationSpec } from '../lib/types';

function SimulationSkeleton() {
  return (
    <div className="grid gap-6 lg:grid-cols-5" aria-label="Running simulation">
      <div className="space-y-6 lg:col-span-3">
        <SkeletonBlock className="h-64 w-full" />
        <div className="grid gap-4 xl:grid-cols-2">
          {Array.from({ length: 4 }, (_, i) => (
            <SkeletonBlock key={i} className="h-40 w-full" />
          ))}
        </div>
      </div>
      <div className="space-y-6 lg:col-span-2">
        <SkeletonBlock className="h-40 w-full" />
      </div>
    </div>
  );
}

export default function SimulatePage() {
  const params = useParams();
  const playerId = Number(params.id);

  const [searchParams, setSearchParams] = useSearchParams();
  const leagueParam = searchParams.get('league');
  const clubParam = searchParams.get('club');
  const clubId = clubParam !== null && /^\d+$/.test(clubParam) ? Number(clubParam) : null;
  const destination: DestinationSpec | null = leagueParam
    ? { league_id: leagueParam, club_id: clubId }
    : null;

  const playerQuery = usePlayer(playerId);
  const destinationsQuery = useDestinations();
  const simulationQuery = useSimulation(playerId, destination);

  const state = deriveSimulatorState({
    destinationSelected: destination !== null,
    isPending: simulationQuery.isPending,
    error: simulationQuery.error,
    data: simulationQuery.data,
  });

  if (
    !Number.isInteger(playerId) ||
    (playerQuery.error instanceof ApiError && playerQuery.error.status === 404)
  ) {
    return (
      <EmptyState
        heading="Player not found"
        action={
          <Link
            to="/search"
            className="rounded border border-pitch-800 bg-pitch-900 px-4 py-2 text-sm text-ink-100 hover:border-brass-400"
          >
            ← Back to search
          </Link>
        }
      />
    );
  }

  const playerName = playerQuery.data?.name ?? null;
  const leagueNames = new Map(
    (destinationsQuery.data?.leagues ?? []).map((league) => [league.league_id, league.name]),
  );

  function setDestination(leagueId: string | null, nextClubId: number | null) {
    const next = new URLSearchParams();
    if (leagueId !== null) {
      next.set('league', leagueId);
      if (nextClubId !== null) next.set('club', String(nextClubId));
    }
    setSearchParams(next);
  }

  return (
    <div className="space-y-6">
      <div>
        <Link to={`/players/${playerId}`} className="text-sm text-ink-400 hover:text-ink-100">
          ← {playerName ?? 'Profile'}
        </Link>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-ink-100">
          Transition Simulator
        </h1>
        <p className="mt-1 text-ink-400">
          Pick a destination — the verdict is built from named, comparable moves and what the market
          did next.
        </p>
      </div>

      <DestinationPicker
        leagues={destinationsQuery.data?.leagues}
        leagueId={leagueParam}
        clubId={clubId}
        onChange={setDestination}
      />

      {state.kind === 'idle' ? (
        <div className="rounded-2xl border border-dashed border-pitch-800 px-6 py-16 text-center">
          <p className="text-lg text-ink-400">
            Pick a destination league to see the verdict — the predicted range, its named precedents
            and the scout&apos;s read appear here.
          </p>
        </div>
      ) : state.kind === 'loading' ? (
        <SimulationSkeleton />
      ) : state.kind === 'no_valuation' ? (
        <NoValuationPanel playerId={playerId} playerName={playerName} />
      ) : state.kind === 'error' ? (
        <EmptyState
          heading="The simulation failed"
          body={state.message}
          action={
            <button
              type="button"
              onClick={() => void simulationQuery.refetch()}
              className="rounded border border-pitch-800 bg-pitch-900 px-4 py-2 text-sm text-ink-100 hover:border-brass-400"
            >
              Retry
            </button>
          }
        />
      ) : state.kind === 'insufficient' ? (
        <div className="grid gap-6 lg:grid-cols-5">
          <div className="lg:col-span-3">
            <InsufficientPanel result={state.result} leagueNames={leagueNames} />
          </div>
          <div className="space-y-6 lg:col-span-2">
            <NarrativeStrip narrative={state.result.narrative} />
            <PoolQualityBanner poolQuality={state.result.pool_quality} />
          </div>
        </div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-5">
          <div className="space-y-6 lg:col-span-3">
            <VerdictPanel result={state.result} prediction={state.prediction} />
            <CompsPanel
              comps={state.result.comps}
              shownComps={state.result.shown_comps}
              leagueNames={leagueNames}
            />
          </div>
          <div className="space-y-6 lg:col-span-2">
            <NarrativeStrip narrative={state.result.narrative} />
            <PoolQualityBanner poolQuality={state.result.pool_quality} />
          </div>
        </div>
      )}
    </div>
  );
}
