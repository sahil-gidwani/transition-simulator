import { useState } from 'react';
import { secondaryAction } from '../components/ui/actions';
import { useNavigate } from 'react-router';
import SearchResultsList from '../components/search/SearchResultsList';
import EmptyState from '../components/ui/EmptyState';
import SkeletonBlock from '../components/ui/SkeletonBlock';
import { useDebouncedValue } from '../hooks/useDebouncedValue';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { useListboxNav } from '../hooks/useListboxNav';
import { usePlayerSearch } from '../lib/queries';
import type { PlayerSearchResult } from '../lib/types';

const LISTBOX_ID = 'player-search-listbox';

function searchOptionId(result: PlayerSearchResult): string {
  return `search-option-${result.player_id}`;
}

export default function SearchPage() {
  useDocumentTitle('Search — Precedent');
  const [input, setInput] = useState('');
  const navigate = useNavigate();
  const q = useDebouncedValue(input, 200);
  const { data, isPending, isError, refetch } = usePlayerSearch(q);

  const searchActive = q.trim().length >= 2;
  const results = (searchActive ? data : undefined) ?? [];

  const { activeIndex, setActiveIndex, activeId, onKeyDown, reset } = useListboxNav({
    items: results,
    makeOptionId: searchOptionId,
    onSelect: (result) => navigate(`/players/${result.player_id}`),
    onEscape: () => setInput(''),
  });

  return (
    <div className="mx-auto max-w-2xl pt-8 sm:pt-20">
      <h1 className="font-display text-5xl font-medium tracking-tight text-balance text-ink-100 sm:text-6xl">
        Every move has a <span className="text-tangerine-300">precedent</span>.
      </h1>
      <p className="mt-5 text-lg leading-relaxed text-ink-400">
        What happens to a player&apos;s value after a move? Precedent answers with evidence: named,
        comparable transitions and what the market did next.
      </p>

      <div className="mt-9">
        <input
          // The hero exists to be typed into; focus is not stolen from anything.
          autoFocus
          role="combobox"
          aria-expanded={searchActive && results.length > 0}
          aria-controls={LISTBOX_ID}
          aria-activedescendant={activeId}
          aria-autocomplete="list"
          aria-label="Search players"
          placeholder="Search any player — name, e.g. Bellingham"
          value={input}
          onChange={(event) => {
            setInput(event.target.value);
            reset();
          }}
          onKeyDown={onKeyDown}
          className="w-full rounded-xl border border-pitch-700 bg-pitch-900/80 px-5 py-4 text-lg text-ink-100 shadow-lg shadow-black/40 transition-shadow duration-150 placeholder:text-ink-500 focus:border-yale-400 focus:shadow-none focus:ring-4 focus:ring-yale-400/25 focus:outline-none"
        />

        {!searchActive ? (
          <p className="mt-3 text-sm text-ink-500">
            Type at least two letters — then arrow keys and Enter take you straight to a profile.
          </p>
        ) : isError ? (
          <div role="alert" className="mt-6 flex flex-col items-center gap-3 py-6 text-center">
            <p className="text-sm text-decline-400">The search request failed.</p>
            <button type="button" onClick={() => void refetch()} className={secondaryAction}>
              Retry
            </button>
          </div>
        ) : isPending && results.length === 0 ? (
          <div
            role="status"
            aria-label="Loading results"
            className="mt-4 divide-y divide-pitch-800 overflow-hidden rounded-xl border border-pitch-800"
          >
            {Array.from({ length: 5 }, (_, i) => (
              <div key={i} className="flex items-center justify-between gap-4 px-4 py-3">
                <div className="flex-1 space-y-2">
                  <SkeletonBlock className="h-4 w-44" />
                  <SkeletonBlock className="h-3 w-64" />
                </div>
                <SkeletonBlock className="h-5 w-16" />
              </div>
            ))}
          </div>
        ) : results.length === 0 ? (
          <EmptyState
            heading={`No players match “${q.trim()}”`}
            body="Precedent covers first-tier leagues in ~30 countries. Try a different spelling — accents don't matter."
          />
        ) : (
          <SearchResultsList
            id={LISTBOX_ID}
            results={results}
            optionId={searchOptionId}
            activeIndex={activeIndex}
            onHover={setActiveIndex}
            onSelect={(result) => navigate(`/players/${result.player_id}`)}
          />
        )}
      </div>
    </div>
  );
}
