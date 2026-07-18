import Badge from '../ui/Badge';
import { formatDate, formatEuroCompact } from '../../lib/format';
import { positionLabel, tierLabel } from '../../lib/labels';
import type { PlayerProfile } from '../../lib/types';
import ValueSparkline from './ValueSparkline';

interface IdentityHeaderProps {
  player: PlayerProfile;
}

export default function IdentityHeader({ player }: IdentityHeaderProps) {
  const meta: string[] = [];
  if (player.age != null) meta.push(`${player.age} yrs`);
  if (player.foot) meta.push(`${player.foot} foot`);
  if (player.height_cm != null) meta.push(`${player.height_cm} cm`);

  const tier = tierLabel(player.league_tier);

  return (
    <section className="flex flex-col gap-6 border-b border-pitch-800 pb-8 lg:flex-row lg:items-end lg:justify-between">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-4xl font-semibold tracking-tight text-ink-100 sm:text-5xl">
            {player.name}
          </h1>
          <Badge variant="accent" title={positionLabel(player.position_group)}>
            {player.position_group}
          </Badge>
          {player.sub_position ? (
            <span className="text-sm text-ink-400">{player.sub_position}</span>
          ) : null}
        </div>
        <p className="mt-3 flex flex-wrap items-center gap-2 text-ink-400">
          <span>
            {player.club_name} · {player.league_name ?? player.league_id}
          </span>
          {tier ? <Badge>{tier}</Badge> : null}
        </p>
        {meta.length > 0 ? <p className="mt-1 text-sm text-ink-500">{meta.join(' · ')}</p> : null}
      </div>

      <div className="shrink-0 lg:text-right">
        <div className="text-4xl font-semibold text-tangerine-200 tabular-nums">
          {formatEuroCompact(player.market_value_eur)}
        </div>
        <div className="mt-1 text-xs text-ink-400">
          {player.market_value_asof
            ? `as of ${formatDate(player.market_value_asof)}`
            : 'no valuation on record'}
        </div>
        <div className="mt-3 lg:ml-auto">
          <ValueSparkline history={player.value_history} />
        </div>
      </div>
    </section>
  );
}
