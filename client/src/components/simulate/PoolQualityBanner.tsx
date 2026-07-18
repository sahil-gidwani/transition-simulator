import { Widen } from '../ui/icons';
import { humanizeRelaxationStep } from '../../lib/relaxation';
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
    similarityCaveats.push("This player's age is unknown, so the matches aren't age-checked.");
  }
  if (poolQuality.missing_minutes) {
    similarityCaveats.push(
      "Playing time before the move is unknown, so it wasn't factored into the matching.",
    );
  }
  if (poolQuality.origin_tier_unknown) {
    similarityCaveats.push(
      "The strength of this player's current league is unknown, so it wasn't matched.",
    );
  }
  if (
    poolQuality.club_selected &&
    poolQuality.dest_elo_available &&
    poolQuality.elo_pool_coverage < LOW_ELO_POOL_COVERAGE
  ) {
    similarityCaveats.push(
      `Only ${Math.round(
        poolQuality.elo_pool_coverage * 100,
      )}% of these moves have club-strength (Elo) ratings — squad value carried the rest.`,
    );
  }
  if (poolQuality.club_indistinct) {
    similarityCaveats.push(
      'Precedent this rare doesn’t distinguish destinations this fine: the club choice barely moves the league-level answer.',
    );
  }

  if (!poolQuality.expanded_search && !eloFallback && similarityCaveats.length === 0) return null;

  return (
    <div className="space-y-4">
      {poolQuality.expanded_search || eloFallback ? (
        <aside className="rounded-xl border border-caution-400/40 bg-caution-400/10 p-4 text-sm">
          {poolQuality.expanded_search ? (
            <>
              <p className="flex items-center gap-1.5 font-semibold text-caution-400">
                <Widen />
                We widened the search
              </p>
              <p className="mt-1 text-ink-100">
                Too few close matches under the strictest criteria, so the net was cast wider:
              </p>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-ink-400">
                {poolQuality.relaxation_steps.map((step) => (
                  // title keeps the server's exact wording as a traceability
                  // breadcrumb behind the plain-language rendering.
                  <li key={step} title={step}>
                    {humanizeRelaxationStep(step)}
                  </li>
                ))}
              </ul>
            </>
          ) : null}
          {eloFallback ? (
            <p className={poolQuality.expanded_search ? 'mt-3 text-ink-400' : 'text-ink-400'}>
              This club has no Elo strength rating on record, so squad value stood in for club
              strength.
            </p>
          ) : null}
        </aside>
      ) : null}

      {similarityCaveats.length > 0 ? (
        <aside className="rounded-xl border border-pitch-800 bg-pitch-900/60 p-4 text-sm">
          <p className="font-semibold text-ink-100">What we couldn&apos;t match</p>
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
