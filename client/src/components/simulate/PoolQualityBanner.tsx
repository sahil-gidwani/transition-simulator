import type { PoolQuality } from '../../lib/types';

interface PoolQualityBannerProps {
  poolQuality: PoolQuality;
}

/**
 * Below this share of Elo-scored comps, an Elo-rated destination club is
 * being compared against a mostly Elo-less pool — the "Elo where available"
 * part of the similarity definition quietly stopped doing its job, so the
 * banner has to say so.
 */
const LOW_ELO_POOL_COVERAGE = 0.5;

/**
 * Surfaces how the comp pool was assembled when that needs saying: the
 * relaxation ladder that widened the search, the Elo fallback for
 * destination clubs without a strength rating, thin Elo coverage across
 * the pool itself, and any query-side nulls that silently weakened the
 * similarity definition (stated-similarity principle: if a filter was
 * skipped, say so). Renders nothing when the base filters produced the
 * pool cleanly.
 */
export default function PoolQualityBanner({ poolQuality }: PoolQualityBannerProps) {
  const eloFallback = poolQuality.club_selected && !poolQuality.dest_elo_available;

  const similarityCaveats: string[] = [];
  if (poolQuality.missing_age) {
    similarityCaveats.push('Age unknown — comps were not age-matched.');
  }
  if (poolQuality.missing_minutes) {
    similarityCaveats.push(
      'Pre-move playing time unknown — the playing-time similarity term was skipped.',
    );
  }
  if (poolQuality.origin_tier_unknown) {
    similarityCaveats.push('Origin league tier unknown — the origin-tier filter was skipped.');
  }
  if (
    poolQuality.club_selected &&
    poolQuality.dest_elo_available &&
    poolQuality.elo_pool_coverage < LOW_ELO_POOL_COVERAGE
  ) {
    similarityCaveats.push(
      `Club-strength (Elo) ratings were available for only ${Math.round(
        poolQuality.elo_pool_coverage * 100,
      )}% of these comparable moves — squad-value tiers carried the rest.`,
    );
  }

  if (!poolQuality.expanded_search && !eloFallback && similarityCaveats.length === 0) return null;

  return (
    <div className="space-y-4">
      {poolQuality.expanded_search || eloFallback ? (
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
              Club-strength (Elo) ratings are unavailable for this destination club — squad-value
              tiers stood in for them.
            </p>
          ) : null}
        </aside>
      ) : null}

      {similarityCaveats.length > 0 ? (
        <aside className="rounded-xl border border-pitch-800 bg-pitch-900/60 p-4 text-sm">
          <p className="font-semibold text-ink-100">Similarity caveats</p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-ink-400">
            {similarityCaveats.map((caveat) => (
              <li key={caveat}>{caveat}</li>
            ))}
          </ul>
        </aside>
      ) : null}
    </div>
  );
}
