import type { ReactNode } from 'react';
import Badge from '../ui/Badge';
import { Clock } from '../ui/icons';
import { formatDate, formatEuroCompact } from '../../lib/format';
import { positionLabel, tierLabel } from '../../lib/labels';
import type { PlayerProfile } from '../../lib/types';

interface IdentityHeaderProps {
  player: PlayerProfile;
}

export default function IdentityHeader({ player }: IdentityHeaderProps) {
  const tier = tierLabel(player.league_tier);

  // Labelled facts, missing ones omitted — never a dash placeholder.
  const facts: { label: string; value: ReactNode }[] = [
    { label: 'Club', value: player.club_name },
    {
      label: 'League',
      value: (
        <span className="inline-flex items-center gap-1.5">
          {player.league_name ?? player.league_id}
          {tier ? (
            <Badge title="League strength: tiers 1–4, from squad values">{tier}</Badge>
          ) : null}
        </span>
      ),
    },
  ];
  if (player.age != null) facts.push({ label: 'Age', value: String(player.age) });
  if (player.foot) facts.push({ label: 'Foot', value: player.foot });
  if (player.height_cm != null) facts.push({ label: 'Height', value: `${player.height_cm} cm` });

  return (
    <section className="flex flex-col gap-6 border-b border-pitch-800 pb-8 lg:flex-row lg:items-end lg:justify-between">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="font-display text-4xl font-medium tracking-tight text-balance text-ink-100 sm:text-5xl">
            {player.name}
          </h1>
          <Badge variant="accent" title={positionLabel(player.position_group)}>
            {player.position_group}
          </Badge>
          {player.sub_position ? (
            <span className="text-sm text-ink-400">{player.sub_position}</span>
          ) : null}
        </div>

        <dl className="mt-5 flex flex-wrap gap-y-3 divide-x divide-pitch-800">
          {facts.map((fact) => (
            <div key={fact.label} className="px-4 first:pl-0 last:pr-0">
              <dt className="text-[11px] font-medium tracking-[0.08em] text-ink-500 uppercase">
                {fact.label}
              </dt>
              <dd className="mt-0.5 text-sm text-ink-100">{fact.value}</dd>
            </div>
          ))}
        </dl>
      </div>

      <div className="shrink-0 lg:text-right">
        <div className="font-display text-5xl font-medium text-tangerine-200 tabular-nums">
          {formatEuroCompact(player.market_value_eur)}
        </div>
        <div className="mt-1.5 flex items-center gap-1 text-xs text-ink-500 lg:justify-end">
          {player.market_value_asof ? (
            <>
              <Clock className="h-2.5 w-2.5" />
              as of {formatDate(player.market_value_asof)}
            </>
          ) : (
            'no valuation on record'
          )}
        </div>
      </div>
    </section>
  );
}
