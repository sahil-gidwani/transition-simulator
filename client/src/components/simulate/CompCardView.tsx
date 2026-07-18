import { Link } from 'react-router';
import Badge from '../ui/Badge';
import Chip from '../ui/Chip';
import { formatAge, formatEuroCompact, formatSeason, formatSignedPct } from '../../lib/format';
import type { CompCard } from '../../lib/types';
import CompSlopeChart from './CompSlopeChart';

interface CompCardViewProps {
  comp: CompCard;
  /** league_id → display name; unknown ids fall back to the raw code. */
  leagueNames?: ReadonlyMap<string, string>;
}

/**
 * One named precedent. Decliners render with identical prominence — red is
 * a color, not a demotion (survivorship principle).
 */
export default function CompCardView({ comp, leagueNames }: CompCardViewProps) {
  const deltaColor =
    comp.delta_pct > 0 ? 'text-rise-400' : comp.delta_pct < 0 ? 'text-decline-400' : 'text-ink-400';
  const leagueName = (id: string) => leagueNames?.get(id) ?? id;

  return (
    <article className="rounded-xl border border-pitch-800 bg-pitch-900 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <Link
            to={`/players/${comp.player_id}`}
            className="font-semibold text-ink-100 hover:text-brass-300"
          >
            {comp.player_name}
          </Link>
          <p className="mt-1 flex flex-wrap items-center gap-x-1.5 text-sm text-ink-400">
            <span>{comp.from_club}</span>
            <span aria-hidden="true">→</span>
            <span>{comp.to_club}</span>
          </p>
          <p className="mt-1.5 flex flex-wrap items-center gap-1.5 text-xs text-ink-500">
            {comp.from_league !== null ? <Badge>{leagueName(comp.from_league)}</Badge> : null}
            <Badge>{leagueName(comp.to_league)}</Badge>
            <span>
              {formatSeason(comp.season)} · age {formatAge(comp.age_at_transfer)} at move
            </span>
          </p>
        </div>
        <span className={`shrink-0 text-2xl font-semibold tabular-nums ${deltaColor}`}>
          {formatSignedPct(comp.delta_pct)}
        </span>
      </div>

      <div className="mt-3 flex items-center gap-4">
        <CompSlopeChart comp={comp} />
        <span className="text-sm text-ink-400 tabular-nums">
          {formatEuroCompact(comp.v_before_eur)} → {formatEuroCompact(comp.v_after_eur)}
        </span>
      </div>

      {comp.tags.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {comp.tags.map((tag) => (
            <Chip key={tag}>{tag}</Chip>
          ))}
        </div>
      ) : null}
    </article>
  );
}
