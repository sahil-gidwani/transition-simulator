import { m } from 'motion/react';
import { useState } from 'react';
import { EASE_OUT } from '../../lib/motion';
import type { CompCard } from '../../lib/types';
import CompCardView from './CompCardView';

interface CompsPanelProps {
  comps: CompCard[];
  /** Server-driven UI default (currently 6); never hardcoded here. */
  shownComps: number;
  leagueNames?: ReadonlyMap<string, string>;
  /** The queried player's age today, for each card's relative-age chip. */
  playerAge?: number | null;
}

export default function CompsPanel({ comps, shownComps, leagueNames, playerAge }: CompsPanelProps) {
  const [expanded, setExpanded] = useState(false);
  const visible = expanded ? comps : comps.slice(0, shownComps);
  // Comps arrive most-similar first, so the head carries the pool's best weight.
  const maxSimilarity = comps[0]?.similarity;

  return (
    <section>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-display text-xl font-medium text-ink-100">The precedent</h2>
        <span className="text-sm text-ink-400">
          {comps.length} comparable move{comps.length === 1 ? '' : 's'}, ordered by similarity
          (decliners included) — the range above is built from exactly these
        </span>
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {visible.map((comp, index) => (
          <m.div
            key={`${comp.player_id}-${comp.transfer_date}`}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.28, ease: EASE_OUT, delay: 0.04 * (index % 12) }}
          >
            <CompCardView
              comp={comp}
              leagueNames={leagueNames}
              maxSimilarity={maxSimilarity}
              playerAge={playerAge}
            />
          </m.div>
        ))}
      </div>

      {comps.length > shownComps ? (
        <m.button
          type="button"
          whileTap={{ scale: 0.98 }}
          onClick={() => setExpanded((value) => !value)}
          className="mt-4 w-full rounded-lg border border-pitch-800 bg-pitch-900 py-2.5 text-sm text-ink-100 transition-colors duration-150 hover:border-yale-400"
        >
          {expanded ? `Show closest ${shownComps} only` : `Show all ${comps.length} precedents`}
        </m.button>
      ) : null}
    </section>
  );
}
