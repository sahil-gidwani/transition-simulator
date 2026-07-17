import { useState } from 'react';
import { useNavigate } from 'react-router';
import SearchResultsList from '../components/search/SearchResultsList';
import EmptyState from '../components/ui/EmptyState';
import SkeletonBlock from '../components/ui/SkeletonBlock';
import { useDebouncedValue } from '../hooks/useDebouncedValue';
import { useListboxNav } from '../hooks/useListboxNav';
import { usePlayerSearch } from '../lib/queries';
import type { PlayerSearchResult } from '../lib/types';

const LISTBOX_ID = 'player-search-listbox';

function searchOptionId(result: PlayerSearchResult): string {
  return `search-option-${result.player_id}`;
}

export default function SearchPage() {
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
    <div className="mx-auto max-w-2xl pt-6 sm:pt-16">
      <p className="text-sm tracking-[0.3em] text-brass-400 uppercase">Transfer valuations</p>
      <h1 className="mt-3 text-4xl font-semibold tracking-tight text-ink-100 sm:text-5xl">
        Every move has a precedent.
      </h1>
      <p className="mt-4 text-lg leading-relaxed text-ink-400">
        What happens to a player&apos;s value after a move? Precedent answers with evidence: named,
        comparable transitions and what the market did next.
      </p>

      <div className="mt-8">
        <input
          // The hero exists to be typed into; focus is not stolen from anything.
          autoFocus
          role="combobox"
          aria-expanded={searchActive}
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
          className="w-full rounded-xl border border-pitch-800 bg-pitch-900 px-5 py-4 text-lg text-ink-100 placeholder:text-ink-400/60 focus:border-brass-400 focus:outline-none"
        />

        {!searchActive ? (
          <p className="mt-3 text-sm text-ink-400/80">
            Type at least two letters — then arrow keys and Enter take you straight to a profile.
          </p>
        ) : isError ? (
          <div className="mt-6 flex flex-col items-center gap-3 py-6 text-center">
            <p className="text-sm text-decline-400">The search request failed.</p>
            <button
              type="button"
              onClick={() => void refetch()}
              className="rounded border border-pitch-800 bg-pitch-900 px-4 py-2 text-sm text-ink-100 hover:border-brass-400"
            >
              Retry
            </button>
          </div>
        ) : isPending && results.length === 0 ? (
          <div className="mt-4 space-y-2" aria-label="Loading results">
            {Array.from({ length: 5 }, (_, i) => (
              <SkeletonBlock key={i} className="h-14 w-full" />
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
