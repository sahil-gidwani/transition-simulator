import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { useListboxNav } from '../../hooks/useListboxNav';

const COMBINING_MARKS = /[̀-ͯ]/g;

function normalize(s: string): string {
  return s.toLowerCase().normalize('NFD').replace(COMBINING_MARKS, '');
}

interface ComboboxProps<T> {
  id: string;
  label: string;
  placeholder: string;
  items: readonly T[];
  itemKey: (item: T) => string | number;
  /** Text the typed filter matches against (diacritic-insensitive). */
  itemText: (item: T) => string;
  renderItem: (item: T) => ReactNode;
  /** Shown in the input while the picker is closed. */
  selectedLabel: string | null;
  onSelect: (item: T) => void;
  disabled?: boolean;
}

/** Searchable single-select: an ARIA combobox over a filtered listbox dropdown. */
export default function Combobox<T>({
  id,
  label,
  placeholder,
  items,
  itemKey,
  itemText,
  renderItem,
  selectedLabel,
  onSelect,
  disabled = false,
}: ComboboxProps<T>) {
  // null = closed; '' = open showing everything; text = open + filtered.
  const [query, setQuery] = useState<string | null>(null);
  const open = query !== null;
  const trimmed = (query ?? '').trim();
  const listItems = !open
    ? []
    : trimmed === ''
      ? items
      : items.filter((item) => normalize(itemText(item)).includes(normalize(trimmed)));

  const nav = useListboxNav({
    items: listItems,
    makeOptionId: (item) => `${id}-option-${itemKey(item)}`,
    onSelect: (item) => {
      onSelect(item);
      setQuery(null);
    },
    onEscape: () => setQuery(null),
  });

  // aria-activedescendant does not scroll on its own; keep the keyboard
  // highlight visible ('nearest' is a no-op for already-visible hover targets).
  useEffect(() => {
    if (!nav.activeId) return;
    const el = document.getElementById(nav.activeId);
    // Guarded: jsdom has no scrollIntoView.
    if (el && typeof el.scrollIntoView === 'function') {
      el.scrollIntoView({ block: 'nearest' });
    }
  }, [nav.activeId]);

  const listboxId = `${id}-listbox`;

  return (
    <div className="relative">
      <label
        htmlFor={id}
        className="block text-xs font-medium tracking-wide text-ink-400 uppercase"
      >
        {label}
      </label>
      <input
        id={id}
        role="combobox"
        aria-expanded={open && listItems.length > 0}
        aria-controls={listboxId}
        aria-activedescendant={nav.activeId}
        aria-autocomplete="list"
        autoComplete="off"
        disabled={disabled}
        placeholder={placeholder}
        value={query ?? selectedLabel ?? ''}
        onFocus={() => setQuery('')}
        onClick={() => {
          if (query === null) setQuery('');
        }}
        onChange={(event) => {
          setQuery(event.target.value);
          nav.reset();
        }}
        onKeyDown={(event) => {
          if (query === null && (event.key === 'ArrowDown' || event.key === 'ArrowUp')) {
            event.preventDefault();
            setQuery('');
            return;
          }
          nav.onKeyDown(event);
        }}
        onBlur={() => setQuery(null)}
        className="mt-1 w-full rounded-lg border border-pitch-800 bg-pitch-900 px-4 py-2.5 text-ink-100 placeholder:text-ink-400/80 focus:border-brass-400 focus:outline-none disabled:cursor-not-allowed disabled:bg-pitch-950 disabled:text-ink-400"
      />
      {open ? (
        listItems.length === 0 ? (
          <div
            role="status"
            className="absolute z-10 mt-1 w-full rounded-lg border border-pitch-800 bg-pitch-900 px-4 py-3 text-sm text-ink-400 shadow-xl"
          >
            No matches
          </div>
        ) : (
          <ul
            id={listboxId}
            role="listbox"
            aria-label={label}
            // Keep focus in the input so blur cannot swallow the option click.
            onMouseDown={(event) => event.preventDefault()}
            className="absolute z-10 mt-1 max-h-72 w-full overflow-auto rounded-lg border border-pitch-800 bg-pitch-900 shadow-xl"
          >
            {listItems.map((item, index) => (
              <li
                key={itemKey(item)}
                id={`${id}-option-${itemKey(item)}`}
                role="option"
                aria-selected={index === nav.activeIndex}
                onMouseEnter={() => nav.setActiveIndex(index)}
                onClick={() => {
                  onSelect(item);
                  setQuery(null);
                  nav.reset();
                }}
                className={`cursor-pointer px-4 py-2.5 ${index === nav.activeIndex ? 'bg-pitch-800' : ''}`}
              >
                {renderItem(item)}
              </li>
            ))}
          </ul>
        )
      ) : null}
    </div>
  );
}
