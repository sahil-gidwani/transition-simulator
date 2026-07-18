import { Link } from 'react-router';
import Badge from '../ui/Badge';
import Chip from '../ui/Chip';
import { ArrowDownRight, ArrowFlat, ArrowUpRight } from '../ui/icons';
import { formatAge, formatEuroCompact, formatSeason, formatSignedPct } from '../../lib/format';
import { compTrend } from '../../lib/trend';
import type { CompCard } from '../../lib/types';
import CompSlopeChart from './CompSlopeChart';

const TREND_STYLE = {
  rise: { color: 'text-rise-400', Icon: ArrowUpRight },
  decline: { color: 'text-decline-400', Icon: ArrowDownRight },
  flat: { color: 'text-ink-400', Icon: ArrowFlat },
} as const;

interface CompCardViewProps {
  comp: CompCard;
  /** league_id → display name; unknown ids fall back to the raw code. */
  leagueNames?: ReadonlyMap<string, string>;
  /** The pool's best similarity; scales the match-strength meter to "best = full". */
  maxSimilarity?: number;
  /** The queried player's age today, for the relative-age chip. */
  playerAge?: number | null;
}

/** "2 yrs younger at move" — the comp's age relative to the queried player. */
function ageDeltaChip(
  ageAtTransfer: number | null,
  playerAge: number | null | undefined,
): string | null {
  if (ageAtTransfer == null || playerAge == null) return null;
  const diff = Math.round(ageAtTransfer - playerAge);
  if (diff === 0) return 'same age at move';
  const unit = Math.abs(diff) === 1 ? 'yr' : 'yrs';
  return `${Math.abs(diff)} ${unit} ${diff < 0 ? 'younger' : 'older'} at move`;
}

/**
 * One named precedent. Decliners render with identical prominence — red is
 * a color, not a demotion (survivorship principle).
 */
export default function CompCardView({
  comp,
  leagueNames,
  maxSimilarity,
  playerAge,
}: CompCardViewProps) {
  const delta = TREND_STYLE[compTrend(comp.delta_pct)];
  const leagueName = (id: string) => leagueNames?.get(id) ?? id;
  const ageChip = ageDeltaChip(comp.age_at_transfer, playerAge);
  // The meter shows the actual quantile weight relative to the pool's best
  // match — an honest "how much this move counts", not a fake percentage.
  const matchShare =
    maxSimilarity != null && maxSimilarity > 0
      ? Math.max(0.04, Math.min(1, comp.similarity / maxSimilarity))
      : null;

  return (
    <article className="flex h-full flex-col rounded-xl border border-pitch-800 bg-pitch-900 p-4 transition-[transform,border-color,box-shadow] duration-150 hover:-translate-y-0.5 hover:border-pitch-700 hover:shadow-lg hover:shadow-black/30">
      <div className="flex items-start justify-between gap-3">
        <Link
          to={`/players/${comp.player_id}`}
          className="min-w-0 truncate font-semibold text-ink-100 hover:text-tangerine-300"
        >
          {comp.player_name}
        </Link>
        <span
          className={`flex shrink-0 items-center gap-1.5 text-2xl font-semibold tabular-nums ${delta.color}`}
        >
          <delta.Icon className="h-4 w-4" />
          {formatSignedPct(comp.delta_pct)}
        </span>
      </div>

      {/* The route wraps as club–league pairs, never as loose badges. */}
      <p className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-ink-400">
        <span className="inline-flex min-w-0 max-w-full items-center gap-1.5">
          <span className="truncate">{comp.from_club}</span>
          {comp.from_league !== null ? <Badge>{leagueName(comp.from_league)}</Badge> : null}
        </span>
        <span aria-hidden="true">→</span>
        <span className="inline-flex min-w-0 max-w-full items-center gap-1.5">
          <span className="truncate">{comp.to_club}</span>
          <Badge>{leagueName(comp.to_league)}</Badge>
        </span>
      </p>
      <p className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-500">
        <span>
          {formatSeason(comp.season)} · age {formatAge(comp.age_at_transfer)} at move
        </span>
        {matchShare != null ? (
          <span
            className="inline-flex items-center gap-1.5"
            title={`Similarity weight ${comp.similarity.toFixed(2)} — how much this move counts in the weighted range (full bar = the pool's closest match)`}
          >
            match
            <span
              data-testid="match-strength"
              className="inline-block h-1 w-14 overflow-hidden rounded-full bg-pitch-800"
            >
              <span
                className="block h-1 rounded-full bg-yale-400"
                style={{ width: `${Math.round(matchShare * 100)}%` }}
              />
            </span>
          </span>
        ) : null}
      </p>

      <div className="mt-3 flex items-center gap-4">
        <CompSlopeChart comp={comp} />
        <span className="text-sm text-ink-400 tabular-nums">
          {formatEuroCompact(comp.v_before_eur)} → {formatEuroCompact(comp.v_after_eur)}
        </span>
      </div>

      {comp.tags.length > 0 || ageChip ? (
        <div className="mt-auto flex flex-wrap gap-1.5 pt-3">
          {ageChip ? <Chip>{ageChip}</Chip> : null}
          {comp.tags.map((tag) => (
            <Chip key={tag}>{tag}</Chip>
          ))}
        </div>
      ) : null}
    </article>
  );
}
