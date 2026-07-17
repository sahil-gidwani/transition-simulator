import { useState } from 'react';
import type { KeyboardEvent } from 'react';

interface ListboxNavOptions<T> {
  items: readonly T[];
  makeOptionId: (item: T, index: number) => string;
  onSelect: (item: T, index: number) => void;
  onEscape?: () => void;
}

/**
 * Keyboard navigation for an ARIA combobox driving a listbox via
 * aria-activedescendant: focus stays in the input; ArrowUp/Down move the
 * highlight, Enter selects, Escape clears. Shared by the player search and
 * the destination picker. Call `reset()` when the query driving `items`
 * changes; a highlight that falls off a shrunken list collapses on its own.
 */
export function useListboxNav<T>({
  items,
  makeOptionId,
  onSelect,
  onEscape,
}: ListboxNavOptions<T>) {
  const [rawIndex, setRawIndex] = useState(-1);
  const activeIndex = rawIndex >= 0 && rawIndex < items.length ? rawIndex : -1;

  function onKeyDown(event: KeyboardEvent) {
    switch (event.key) {
      case 'ArrowDown':
        if (items.length > 0) {
          event.preventDefault();
          setRawIndex(Math.min(activeIndex + 1, items.length - 1));
        }
        break;
      case 'ArrowUp':
        if (items.length > 0) {
          event.preventDefault();
          setRawIndex(Math.max(activeIndex - 1, 0));
        }
        break;
      case 'Enter': {
        const item = items[activeIndex];
        if (item !== undefined) {
          event.preventDefault();
          onSelect(item, activeIndex);
        }
        break;
      }
      case 'Escape':
        event.preventDefault();
        setRawIndex(-1);
        onEscape?.();
        break;
    }
  }

  const activeItem = items[activeIndex];
  const activeId = activeItem !== undefined ? makeOptionId(activeItem, activeIndex) : undefined;

  return {
    activeIndex,
    setActiveIndex: setRawIndex,
    activeId,
    onKeyDown,
    reset: () => setRawIndex(-1),
  };
}
