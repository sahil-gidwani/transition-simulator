import Chip from '../ui/Chip';
import { NoRange } from '../ui/icons';
import type { SimulationResponse } from '../../lib/types';
import CompCardView from './CompCardView';

interface InsufficientPanelProps {
  result: SimulationResponse;
  leagueNames?: ReadonlyMap<string, string>;
}

/** The honest refusal: fewer than two usable comps means no range at all. */
export default function InsufficientPanel({ result, leagueNames }: InsufficientPanelProps) {
  return (
    <section className="glass-panel rounded-2xl p-6 sm:p-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-display text-3xl font-medium text-ink-100">Insufficient precedent</h2>
        <Chip tone="decline" icon={<NoRange />}>
          No range
        </Chip>
      </div>
      <p className="mt-3 max-w-xl leading-relaxed text-ink-400">
        Fewer than two comparable transitions survive the similarity checks for this move, even
        after widening the search. Precedent doesn&apos;t invent a range from thin evidence.
      </p>

      {result.comps.length > 0 ? (
        <div className="mt-6">
          <p className="flex items-center gap-2 text-sm font-semibold text-ink-100">
            The closest we have
            <Chip tone="caution">not enough to price</Chip>
          </p>
          <div className="mt-3 grid gap-4 sm:max-w-md">
            {result.comps.map((comp) => (
              <CompCardView
                key={`${comp.player_id}-${comp.transfer_date}`}
                comp={comp}
                leagueNames={leagueNames}
              />
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}
