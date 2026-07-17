import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { KeyboardEvent } from 'react';
import { useListboxNav } from './useListboxNav';

function key(name: string): KeyboardEvent {
  return { key: name, preventDefault: vi.fn() } as unknown as KeyboardEvent;
}

function setup(items: string[]) {
  const onSelect = vi.fn<(item: string, index: number) => void>();
  const onEscape = vi.fn<() => void>();
  const hook = renderHook(
    ({ current }: { current: string[] }) =>
      useListboxNav({
        items: current,
        makeOptionId: (item) => `opt-${item}`,
        onSelect,
        onEscape,
      }),
    { initialProps: { current: items } },
  );
  return { ...hook, onSelect, onEscape };
}

describe('useListboxNav', () => {
  it('clamps ArrowDown at the last item without wrapping', () => {
    const { result } = setup(['a', 'b']);
    act(() => result.current.onKeyDown(key('ArrowDown')));
    act(() => result.current.onKeyDown(key('ArrowDown')));
    act(() => result.current.onKeyDown(key('ArrowDown')));
    expect(result.current.activeIndex).toBe(1);
    expect(result.current.activeId).toBe('opt-b');
  });

  it('lands ArrowUp on the first item from no highlight and clamps at 0', () => {
    const { result } = setup(['a', 'b']);
    act(() => result.current.onKeyDown(key('ArrowUp')));
    expect(result.current.activeIndex).toBe(0);
    act(() => result.current.onKeyDown(key('ArrowUp')));
    expect(result.current.activeIndex).toBe(0);
  });

  it('does nothing on Enter with no highlight or an empty list', () => {
    const { result, onSelect } = setup(['a', 'b']);
    act(() => result.current.onKeyDown(key('Enter')));
    expect(onSelect).not.toHaveBeenCalled();

    const empty = setup([]);
    act(() => empty.result.current.onKeyDown(key('Enter')));
    expect(empty.onSelect).not.toHaveBeenCalled();
  });

  it('selects the highlighted item on Enter and clears the highlight', () => {
    const { result, onSelect } = setup(['a', 'b']);
    act(() => result.current.onKeyDown(key('ArrowDown')));
    act(() => result.current.onKeyDown(key('ArrowDown')));
    act(() => result.current.onKeyDown(key('Enter')));
    expect(onSelect).toHaveBeenCalledWith('b', 1);
    expect(result.current.activeIndex).toBe(-1);
  });

  it('collapses a highlight that falls off a shrunken list', () => {
    const { result, rerender, onSelect } = setup(['a', 'b', 'c']);
    act(() => result.current.onKeyDown(key('ArrowDown')));
    act(() => result.current.onKeyDown(key('ArrowDown')));
    act(() => result.current.onKeyDown(key('ArrowDown')));
    expect(result.current.activeIndex).toBe(2);

    rerender({ current: ['a'] });
    expect(result.current.activeIndex).toBe(-1);
    expect(result.current.activeId).toBeUndefined();
    act(() => result.current.onKeyDown(key('Enter')));
    expect(onSelect).not.toHaveBeenCalled();
  });

  it('resets the highlight and calls onEscape on Escape', () => {
    const { result, onEscape } = setup(['a', 'b']);
    act(() => result.current.onKeyDown(key('ArrowDown')));
    act(() => result.current.onKeyDown(key('Escape')));
    expect(result.current.activeIndex).toBe(-1);
    expect(onEscape).toHaveBeenCalledOnce();
  });
});
