import Badge from '../ui/Badge';
import { Clock } from '../ui/icons';
import { formatDate, formatEuroCompact } from '../../lib/format';
import { positionLabel } from '../../lib/labels';
import type { PlayerSearchResult } from '../../lib/types';

interface SearchResultsListProps {
  id: string;
  results: PlayerSearchResult[];
  optionId: (result: PlayerSearchResult) => string;
  activeIndex: number;
  onHover: (index: number) => void;
  onSelect: (result: PlayerSearchResult) => void;
}

export default function SearchResultsList({
  id,
  results,
  optionId,
  activeIndex,
  onHover,
  onSelect,
}: SearchResultsListProps) {
  return (
    <ul
      id={id}
      role="listbox"
      aria-label="Player results"
      className="mt-4 divide-y divide-pitch-800/70 overflow-hidden rounded-xl border border-pitch-800 bg-pitch-900/60 shadow-xl shadow-black/30"
    >
      {results.map((result, index) => (
        <li
          key={result.player_id}
          id={optionId(result)}
          role="option"
          aria-selected={index === activeIndex}
          className={`flex cursor-pointer items-center justify-between gap-4 px-4 py-3 ${
            index === activeIndex ? 'bg-pitch-800' : 'hover:bg-pitch-900'
          }`}
          onMouseEnter={() => onHover(index)}
          onClick={() => onSelect(result)}
        >
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="truncate font-semibold text-ink-100">{result.name}</span>
              <Badge title={positionLabel(result.position_group)}>{result.position_group}</Badge>
              {result.age != null ? (
                <span className="text-sm whitespace-nowrap text-ink-400">{result.age} yrs</span>
              ) : null}
            </div>
            <div className="mt-0.5 truncate text-sm text-ink-400">
              {result.club_name} · {result.league_name ?? result.league_id}
            </div>
          </div>
          <span className="shrink-0 text-right">
            <span className="block font-medium text-tangerine-200 tabular-nums">
              {formatEuroCompact(result.market_value_eur)}
            </span>
            <span className="flex items-center justify-end gap-1 text-xs whitespace-nowrap text-ink-500">
              {result.market_value_asof ? (
                <>
                  <Clock className="h-2.5 w-2.5" />
                  as of {formatDate(result.market_value_asof)}
                </>
              ) : (
                'no valuation on record'
              )}
            </span>
          </span>
        </li>
      ))}
    </ul>
  );
}
