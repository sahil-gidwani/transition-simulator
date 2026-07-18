import { Link, useParams } from 'react-router';
import { secondaryAction, secondaryActionCompact } from '../components/ui/actions';
import IdentityHeader from '../components/player/IdentityHeader';
import MarketValueChart from '../components/player/MarketValueChart';
import PercentileBars from '../components/player/PercentileBars';
import Chip from '../components/ui/Chip';
import EmptyState from '../components/ui/EmptyState';
import SkeletonBlock from '../components/ui/SkeletonBlock';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { ApiError } from '../lib/api';
import { formatEuroCompact, formatSignedPct } from '../lib/format';
import { usePercentiles, usePlayer } from '../lib/queries';
import { compTrend } from '../lib/trend';
import { valueFacts } from '../lib/valueFacts';

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
        {/* Identity header: name row + fact strip left, value block right. */}
        <div className="flex items-end justify-between border-b border-pitch-800 pb-8">
          <div className="space-y-4">
            <SkeletonBlock className="h-12 w-72" />
            <SkeletonBlock className="h-10 w-96 max-w-full" />
          </div>
          <SkeletonBlock className="h-20 w-56" />
        </div>
        {/* CTA band, then the chart + percentile panels. */}
        <SkeletonBlock className="h-28 w-full rounded-2xl" />
        <div className="grid gap-6 xl:grid-cols-5">
          <SkeletonBlock className="h-80 w-full rounded-2xl xl:col-span-3" />
          <SkeletonBlock className="h-80 w-full rounded-2xl xl:col-span-2" />
        </div>
      </div>
    );
  }

  const player = playerQuery.data;
  const canSimulate = player.market_value_eur != null;
  const facts = valueFacts(player.value_history);
  const trend12m = facts?.delta12mPct != null ? compTrend(facts.delta12mPct) : null;

  return (
    <div className="space-y-8">
      <IdentityHeader player={player} />

      {canSimulate ? (
        <section className="gradient-border flex flex-col gap-5 rounded-2xl p-6 sm:flex-row sm:items-center sm:justify-between sm:p-7">
          <div>
            <h2 className="font-display text-2xl font-medium text-ink-100">
              What would a move do to {formatEuroCompact(player.market_value_eur)}?
            </h2>
            <p className="mt-1 text-sm text-ink-400">
              Pick a destination — a range built from named precedents.
            </p>
          </div>
          <Link
            to={`/players/${player.player_id}/simulate`}
            className="inline-flex shrink-0 items-center gap-2 rounded-lg bg-tangerine-300 px-6 py-3.5 text-base font-semibold text-pitch-950 transition-transform duration-150 hover:bg-tangerine-200 active:scale-[0.98]"
          >
            Simulate a transfer →
          </Link>
        </section>
      ) : (
        // Same band, muted: the missing-valuation honesty note keeps the
        // hero slot, it just cannot wear the invitation ring.
        <section className="flex flex-col gap-5 rounded-2xl border border-pitch-800 bg-pitch-900/60 p-6 sm:flex-row sm:items-center sm:justify-between sm:p-7">
          <div>
            <h2 className="font-display text-2xl font-medium text-ink-100">
              What would a move do to this value?
            </h2>
            <p id="simulate-disabled-reason" className="mt-1 text-sm text-ink-400">
              Needs a current market value to anchor the predicted range — none on record.
            </p>
          </div>
          <button
            type="button"
            disabled
            aria-describedby="simulate-disabled-reason"
            className="inline-flex shrink-0 cursor-not-allowed items-center gap-2 rounded-lg bg-pitch-800 px-6 py-3.5 text-base font-semibold text-ink-400"
          >
            Simulate a transfer →
          </button>
        </section>
      )}

      <div className="grid gap-6 xl:grid-cols-5">
        <section className="rounded-2xl border border-pitch-800 bg-pitch-900/40 p-6 xl:col-span-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-display text-xl font-medium text-ink-100">Market value</h2>
            {facts ? (
              <div className="flex flex-wrap gap-1.5">
                <Chip>
                  peak {formatEuroCompact(facts.peakValue)} ({facts.peakDate.slice(0, 4)})
                </Chip>
                {facts.sincePeakPct < 0 ? (
                  <Chip tone="decline">{formatSignedPct(facts.sincePeakPct)} since peak</Chip>
                ) : (
                  <Chip tone="rise">at peak</Chip>
                )}
                {facts.delta12mPct != null && trend12m != null ? (
                  <Chip tone={trend12m === 'flat' ? 'neutral' : trend12m}>
                    {formatSignedPct(facts.delta12mPct)} in 12 mo
                  </Chip>
                ) : null}
              </div>
            ) : null}
          </div>
          <div className="mt-4">
            <MarketValueChart history={player.value_history} transfers={player.transfers} />
          </div>
        </section>

        <div className="rounded-2xl border border-pitch-800 bg-pitch-900/40 p-6 xl:col-span-2">
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
      </div>
    </div>
  );
}
