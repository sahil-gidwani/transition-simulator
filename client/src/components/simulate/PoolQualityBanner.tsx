import type { PoolQuality } from '../../lib/types';

interface PoolQualityBannerProps {
  poolQuality: PoolQuality;
}

/**
 * Surfaces how the comp pool was assembled when that needs saying: the
 * relaxation ladder that widened the search, and the Elo fallback for
 * destination clubs without a strength rating. Renders nothing when the
 * base filters produced the pool cleanly.
 */
export default function PoolQualityBanner({ poolQuality }: PoolQualityBannerProps) {
  const eloFallback = poolQuality.club_selected && !poolQuality.dest_elo_available;
  if (!poolQuality.expanded_search && !eloFallback) return null;

  return (
    <aside className="rounded-xl border border-caution-400/40 bg-caution-400/10 p-4 text-sm">
      {poolQuality.expanded_search ? (
        <>
          <p className="font-semibold text-caution-400">Expanded search</p>
          <p className="mt-1 text-ink-100">
            Thin precedent at the strictest filters — the search was widened to build this pool:
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-ink-400">
            {poolQuality.relaxation_steps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ul>
        </>
      ) : null}
      {eloFallback ? (
        <p className={poolQuality.expanded_search ? 'mt-3 text-ink-400' : 'text-ink-400'}>
          Club-strength (Elo) ratings are unavailable for this destination club — squad-value tiers
          stood in for them.
        </p>
      ) : null}
    </aside>
  );
}
