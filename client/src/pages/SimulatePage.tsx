import { Link, useParams, useSearchParams } from 'react-router';
import { secondaryAction, secondaryActionCompact } from '../components/ui/actions';
import CompsPanel from '../components/simulate/CompsPanel';
import DestinationPicker from '../components/simulate/DestinationPicker';
import InsufficientPanel from '../components/simulate/InsufficientPanel';
import NarrativeStrip from '../components/simulate/NarrativeStrip';
import NoValuationPanel from '../components/simulate/NoValuationPanel';
import PoolQualityBanner from '../components/simulate/PoolQualityBanner';
import VerdictPanel from '../components/simulate/VerdictPanel';
import Logo from '../components/layout/Logo';
import EmptyState from '../components/ui/EmptyState';
import SkeletonBlock from '../components/ui/SkeletonBlock';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { ApiError } from '../lib/api';
import { useDestinations, usePlayer, useSimulation } from '../lib/queries';
import { deriveSimulatorState } from '../lib/simulatorState';
import type { DestinationSpec } from '../lib/types';

function SimulationSkeleton() {
  return (
    <div role="status" className="space-y-6" aria-label="Running simulation">
      <div className="grid gap-6 lg:grid-cols-5">
        {/* Mirrors the verdict hero: header row, big range, range band, footnote. */}
        <div className="space-y-5 rounded-2xl border border-pitch-800 bg-pitch-900 p-6 sm:p-8 lg:col-span-3">
          <div className="flex items-center justify-between gap-3">
            <SkeletonBlock className="h-4 w-64" />
            <SkeletonBlock className="h-6 w-32 rounded-full" />
          </div>
          <SkeletonBlock className="mx-auto h-16 w-3/4" />
          <SkeletonBlock className="h-8 w-full" />
          <SkeletonBlock className="h-4 w-52" />
        </div>
        <div className="space-y-6 lg:col-span-2">
          <SkeletonBlock className="h-44 w-full rounded-xl" />
          <SkeletonBlock className="h-28 w-full rounded-xl" />
        </div>
      </div>
      {/* Mirrors the full-width precedent grid. */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 6 }, (_, i) => (
          <SkeletonBlock key={i} className="h-44 w-full rounded-xl" />
        ))}
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
  useDocumentTitle(
    playerQuery.data ? `Simulate ${playerQuery.data.name} — Precedent` : 'Simulate — Precedent',
  );

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
          <Link to="/search" className={secondaryAction}>
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
        <h1 className="mt-2 font-display text-4xl font-medium tracking-tight text-ink-100">
          Transition Simulator
        </h1>
        <p className="mt-1 text-ink-400">
          Pick a destination — the verdict is built from named, comparable moves and what the market
          did next.
        </p>
      </div>

      {destinationsQuery.isError ? (
        <div
          role="alert"
          className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-pitch-800 bg-pitch-900/60 p-4 text-sm"
        >
          <span className="text-decline-400">Could not load the destination leagues.</span>
          <button
            type="button"
            onClick={() => void destinationsQuery.refetch()}
            className={secondaryActionCompact}
          >
            Retry
          </button>
        </div>
      ) : (
        <DestinationPicker
          leagues={destinationsQuery.data?.leagues}
          leagueId={leagueParam}
          clubId={clubId}
          onChange={setDestination}
        />
      )}

      {state.kind === 'idle' ? (
        <div className="rounded-2xl border border-dashed border-pitch-700 px-6 py-16 text-center">
          <Logo variant="mark" decorative className="mx-auto h-10 w-10 opacity-40" />
          <p className="mx-auto mt-4 max-w-xl text-lg text-ink-400">
            Pick a destination league to see the verdict — the predicted range, the named moves
            behind it, and the scout&apos;s read appear here.
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
              className={secondaryAction}
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
        <>
          <div className="grid gap-6 lg:grid-cols-5">
            <div className="lg:col-span-3">
              <VerdictPanel result={state.result} prediction={state.prediction} />
            </div>
            <div className="space-y-6 lg:col-span-2">
              <NarrativeStrip narrative={state.result.narrative} />
              <PoolQualityBanner poolQuality={state.result.pool_quality} />
            </div>
          </div>
          <CompsPanel
            // Re-key per player+destination so the expand-all toggle never
            // leaks across cached destination or player switches.
            key={`${playerId}-${state.result.destination.league_id}-${state.result.destination.club_id ?? 'any'}`}
            comps={state.result.comps}
            shownComps={state.result.shown_comps}
            leagueNames={leagueNames}
          />
        </>
      )}
    </div>
  );
}
