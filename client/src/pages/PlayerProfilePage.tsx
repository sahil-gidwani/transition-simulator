import { Link, useParams } from 'react-router';
import IdentityHeader from '../components/player/IdentityHeader';
import PercentileBars from '../components/player/PercentileBars';
import EmptyState from '../components/ui/EmptyState';
import SkeletonBlock from '../components/ui/SkeletonBlock';
import { ApiError } from '../lib/api';
import { usePercentiles, usePlayer } from '../lib/queries';

function BackToSearch() {
  return (
    <Link
      to="/search"
      className="rounded border border-pitch-800 bg-pitch-900 px-4 py-2 text-sm text-ink-100 hover:border-brass-400"
    >
      ← Back to search
    </Link>
  );
}

export default function PlayerProfilePage() {
  const params = useParams();
  const playerId = Number(params.id);
  const playerQuery = usePlayer(playerId);
  const percentilesQuery = usePercentiles(playerId);

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
              className="rounded border border-pitch-800 bg-pitch-900 px-4 py-2 text-sm text-ink-100 hover:border-brass-400"
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
      <div className="space-y-8" aria-label="Loading profile">
        <div className="flex items-end justify-between border-b border-pitch-800 pb-8">
          <div className="space-y-3">
            <SkeletonBlock className="h-12 w-72" />
            <SkeletonBlock className="h-4 w-56" />
          </div>
          <SkeletonBlock className="h-24 w-56" />
        </div>
        <SkeletonBlock className="h-48 w-full" />
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
            className="inline-flex items-center gap-2 rounded-lg bg-brass-400 px-5 py-3 text-base font-semibold text-pitch-950 hover:bg-brass-300"
          >
            Simulate a transfer →
          </Link>
        ) : (
          <span
            aria-disabled="true"
            title="A simulation needs a current market value to anchor the predicted range — none on record."
            className="inline-flex cursor-not-allowed items-center gap-2 rounded-lg bg-pitch-800 px-5 py-3 text-base font-semibold text-ink-400"
          >
            Simulate a transfer →
          </span>
        )}
      </div>

      {percentilesQuery.isPending ? (
        <div className="space-y-3" aria-label="Loading percentiles">
          <SkeletonBlock className="h-6 w-56" />
          {Array.from({ length: 4 }, (_, i) => (
            <SkeletonBlock key={i} className="h-6 w-full" />
          ))}
        </div>
      ) : percentilesQuery.isError ? (
        <p className="text-sm text-ink-400">Peer percentiles are unavailable right now.</p>
      ) : (
        <PercentileBars percentiles={percentilesQuery.data} />
      )}
    </div>
  );
}
