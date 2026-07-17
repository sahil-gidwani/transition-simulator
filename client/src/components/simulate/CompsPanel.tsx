import { useState } from 'react';
import type { CompCard } from '../../lib/types';
import CompCardView from './CompCardView';

interface CompsPanelProps {
  comps: CompCard[];
  /** Server-driven UI default (currently 6); never hardcoded here. */
  shownComps: number;
  leagueNames?: ReadonlyMap<string, string>;
}

export default function CompsPanel({ comps, shownComps, leagueNames }: CompsPanelProps) {
  const [expanded, setExpanded] = useState(false);
  const visible = expanded ? comps : comps.slice(0, shownComps);

  return (
    <section>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-semibold text-ink-100">The precedent</h2>
        <span className="text-sm text-ink-400">
          {comps.length} comparable move{comps.length === 1 ? '' : 's'} — the range is computed from
          exactly these
        </span>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        {visible.map((comp) => (
          <CompCardView
            key={`${comp.player_id}-${comp.transfer_date}`}
            comp={comp}
            leagueNames={leagueNames}
          />
        ))}
      </div>

      {comps.length > shownComps ? (
        <button
          type="button"
          onClick={() => setExpanded((value) => !value)}
          className="mt-4 w-full rounded-lg border border-pitch-800 bg-pitch-900 py-2.5 text-sm text-ink-100 hover:border-brass-400"
        >
          {expanded ? `Show closest ${shownComps} only` : `Show all ${comps.length} precedents`}
        </button>
      ) : null}
    </section>
  );
}
