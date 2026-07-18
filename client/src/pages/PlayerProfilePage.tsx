import { Link, useParams } from 'react-router';
import { secondaryAction, secondaryActionCompact } from '../components/ui/actions';
import IdentityHeader from '../components/player/IdentityHeader';
import MarketValueChart from '../components/player/MarketValueChart';
import PercentileBars from '../components/player/PercentileBars';
import EmptyState from '../components/ui/EmptyState';
import SkeletonBlock from '../components/ui/SkeletonBlock';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { ApiError } from '../lib/api';
import { usePercentiles, usePlayer } from '../lib/queries';

function BackToSearch() {
  return (
    <Link to="/search" className={secondaryAction}>
      ← Back to search
    </Link>
  );
}

export default function PlayerProfilePage() {
  const params = useParams();
  const playerId = Number(params.id);
  const playerQuery = usePlayer(playerId);
  const percentilesQuery = usePercentiles(playerId);
  useDocumentTitle(playerQuery.data ? `${playerQuery.data.name} — Precedent` : null);

  if (!Number.isInteger(playerId)) {
    return <EmptyState heading="Player not found" action={<BackToSearch />} />;
  }

  if (playerQuery.isError) {
    const notFound = playerQuery.error instanceof ApiError && playerQuery.error.status === 404;
    return (
      <EmptyState
        heading={notFound ? 'Player not found' : 'Could not load this player'}
        body={notFound ? 'No player with that id is in the covered leagues.' : undefined}
        action={
          notFound ? (
            <BackToSearch />
          ) : (
            <button
              type="button"
              onClick={() => void playerQuery.refetch()}
              className={secondaryAction}
            >
              Retry
            </button>
          )
        }
      />
    );
  }

  if (playerQuery.isPending) {
    return (
      <div role="status" className="space-y-8" aria-label="Loading profile">
        <div className="flex items-end justify-between border-b border-pitch-800 pb-8">
          <div className="space-y-3">
            <SkeletonBlock className="h-12 w-72" />
            <SkeletonBlock className="h-4 w-56" />
            <SkeletonBlock className="h-4 w-40" />
          </div>
          <SkeletonBlock className="h-20 w-56" />
        </div>
        <SkeletonBlock className="h-12 w-56 rounded-lg" />
        <SkeletonBlock className="h-64 w-full rounded-2xl" />
        <div className="space-y-3">
          <SkeletonBlock className="h-6 w-56" />
          {Array.from({ length: 4 }, (_, i) => (
            <SkeletonBlock key={i} className="h-6 w-full" />
          ))}
        </div>
      </div>
    );
  }

  const player = playerQuery.data;
  const canSimulate = player.market_value_eur != null;

  return (
    <div className="space-y-8">
      <IdentityHeader player={player} />

      <div>
        {canSimulate ? (
          <Link
            to={`/players/${player.player_id}/simulate`}
            className="inline-flex items-center gap-2 rounded-lg bg-tangerine-300 px-5 py-3 text-base font-semibold text-pitch-950 transition-transform duration-150 hover:bg-tangerine-200 active:scale-[0.98]"
          >
            Simulate a transfer →
          </Link>
        ) : (
          <>
            <button
              type="button"
              disabled
              aria-describedby="simulate-disabled-reason"
              className="inline-flex cursor-not-allowed items-center gap-2 rounded-lg bg-pitch-800 px-5 py-3 text-base font-semibold text-ink-400"
            >
              Simulate a transfer →
            </button>
            <p id="simulate-disabled-reason" className="mt-2 text-sm text-ink-400">
              Needs a current market value to anchor the predicted range — none on record.
            </p>
          </>
        )}
      </div>

      <section>
        <h2 className="font-display text-xl font-medium text-ink-100">Market value</h2>
        <div className="mt-4">
          <MarketValueChart history={player.value_history} />
        </div>
      </section>

      {percentilesQuery.isPending ? (
        <div role="status" className="space-y-3" aria-label="Loading percentiles">
          <SkeletonBlock className="h-6 w-56" />
          {Array.from({ length: 4 }, (_, i) => (
            <SkeletonBlock key={i} className="h-6 w-full" />
          ))}
        </div>
      ) : percentilesQuery.isError ? (
        <div role="alert" className="flex items-center gap-4">
          <p className="text-sm text-ink-400">Peer percentiles are unavailable right now.</p>
          <button
            type="button"
            onClick={() => void percentilesQuery.refetch()}
            className={secondaryActionCompact}
          >
            Retry
          </button>
        </div>
      ) : (
        <PercentileBars
          percentiles={percentilesQuery.data}
          leagueLabel={
            percentilesQuery.data.league_id === null
              ? null
              : percentilesQuery.data.league_id === player.league_id
                ? (player.league_name ?? player.league_id)
                : percentilesQuery.data.league_id
          }
        />
      )}
    </div>
  );
}
