import EmptyState from '../ui/EmptyState';
import { formatSeason } from '../../lib/format';
import type { MetricPercentile, PercentilesResponse } from '../../lib/types';

function formatMetricValue(metric: MetricPercentile): string {
  if (metric.value == null) return '—';
  if (metric.metric === 'clean_sheet_rate') return `${Math.round(metric.value * 100)}%`;
  return metric.value.toFixed(2);
}

interface PercentileBarsProps {
  percentiles: PercentilesResponse;
  /**
   * Display label for the league the peer group was drawn from (the latest
   * STATS season's league, which can differ from the player's current league
   * after a recent transfer). Null omits the league from the copy.
   */
  leagueLabel?: string | null;
}

/**
 * "Performance vs peers" — horizontal percentile bars. The server's
 * percentiles are already display-oriented (always "better than X% of
 * peers", including lower-is-better metrics), so they render as-is.
 */
export default function PercentileBars({ percentiles, leagueLabel = null }: PercentileBarsProps) {
  if (!percentiles.has_stats || percentiles.metrics.length === 0) {
    return (
      <EmptyState
        heading="No league appearance data on record"
        body="Percentiles need league minutes; this player has none in the covered seasons."
      />
    );
  }

  const peerN = percentiles.metrics[0]?.peer_n;
  const subtext = [
    percentiles.season != null ? `${formatSeason(percentiles.season)} season` : null,
    percentiles.minutes != null
      ? `${percentiles.minutes.toLocaleString('en-GB')} minutes played`
      : null,
    peerN != null
      ? `against ${peerN} players in the same position${leagueLabel ? ` in ${leagueLabel}` : ''}`
      : null,
  ]
    .filter(Boolean)
    .join(' · ');

  return (
    <section>
      <h2 className="font-display text-xl font-medium text-ink-100">How they compare</h2>
      <p className="mt-1 text-sm text-ink-400">{subtext}</p>
      {percentiles.below_floor ? (
        <p className="mt-2 text-sm text-caution-400">
          Too few minutes this season for a fair ranking — numbers shown, rankings withheld.
        </p>
      ) : null}

      <ul className="mt-5 space-y-4">
        {percentiles.metrics.map((metric) => (
          <li
            key={metric.metric}
            className="grid grid-cols-[minmax(5.5rem,11rem)_1fr_auto] items-center gap-x-4"
          >
            <div className="min-w-0">
              <span className="text-sm text-ink-100">{metric.label}</span>
              {metric.direction === 'lower_better' ? (
                <span className="block text-xs text-ink-400">lower is better</span>
              ) : null}
            </div>

            {metric.percentile != null ? (
              <>
                <div className="h-2.5 overflow-hidden rounded-full bg-pitch-800">
                  <div
                    data-testid={`percentile-fill-${metric.metric}`}
                    className="percentile-fill h-2.5 rounded-full"
                    style={{ width: `${metric.percentile}%` }}
                  />
                </div>
                <div className="flex items-baseline justify-end gap-3">
                  <span className="text-sm text-ink-400 tabular-nums">
                    {formatMetricValue(metric)}
                  </span>
                  <span
                    className="w-8 text-right text-base font-semibold text-ink-100 tabular-nums"
                    title={`Better than ${metric.percentile}% of comparable players`}
                  >
                    {metric.percentile}
                  </span>
                </div>
              </>
            ) : (
              <div className="col-span-2 text-sm text-ink-400">
                <span className="tabular-nums">{formatMetricValue(metric)}</span>
                <span className="ml-2 text-xs text-ink-400">not ranked — too few minutes</span>
              </div>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
