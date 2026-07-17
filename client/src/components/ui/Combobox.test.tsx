import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import Combobox from './Combobox';

interface League {
  id: string;
  name: string;
}

const LEAGUES: League[] = [
  { id: 'BR1', name: 'Série A' },
  { id: 'GB1', name: 'Premier League' },
  { id: 'IT1', name: 'Serie A' },
];

function renderCombobox(overrides: { selectedLabel?: string | null } = {}) {
  const onSelect = vi.fn<(item: League) => void>();
  render(
    <Combobox<League>
      id="league"
      label="Destination league"
      placeholder="Search leagues…"
      items={LEAGUES}
      itemKey={(l) => l.id}
      itemText={(l) => l.name}
      renderItem={(l) => <span>{l.name}</span>}
      selectedLabel={overrides.selectedLabel ?? null}
      onSelect={onSelect}
    />,
  );
  return { onSelect, input: screen.getByRole('combobox') };
}

describe('Combobox', () => {
  it('shows the selected label while closed and opens with all items on focus', () => {
    const { input } = renderCombobox({ selectedLabel: 'Premier League — England' });
    expect(input).toHaveValue('Premier League — England');

    fireEvent.focus(input);
    expect(screen.getAllByRole('option')).toHaveLength(3);
  });

  it('filters diacritic-insensitively', () => {
    const { input } = renderCombobox();
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: 'serie' } });

    // 'serie' matches both 'Série A' (via NFD stripping) and 'Serie A'.
    const options = screen.getAllByRole('option');
    expect(options).toHaveLength(2);
    expect(options[0]).toHaveTextContent('Série A');
  });

  it('selects on option click despite the input blur race, then closes', () => {
    const { input, onSelect } = renderCombobox();
    fireEvent.focus(input);
    const option = screen.getByRole('option', { name: 'Premier League' });

    // The listbox preventDefaults mousedown so blur cannot close it pre-click.
    const mouseDownEvent = fireEvent.mouseDown(option.parentElement!);
    expect(mouseDownEvent).toBe(false); // defaultPrevented
    fireEvent.click(option);

    expect(onSelect).toHaveBeenCalledWith(LEAGUES[1]);
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
  });

  it('selects with keyboard and clears the highlight for the next open', () => {
    const { input, onSelect } = renderCombobox();
    fireEvent.focus(input);
    fireEvent.keyDown(input, { key: 'ArrowDown' });
    fireEvent.keyDown(input, { key: 'ArrowDown' });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onSelect).toHaveBeenCalledWith(LEAGUES[1]);
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();

    // Reopen: no stale highlight from the previous selection.
    fireEvent.keyDown(input, { key: 'ArrowDown' });
    const selected = screen
      .getAllByRole('option')
      .filter((o) => o.getAttribute('aria-selected') === 'true');
    expect(selected).toHaveLength(0);
  });

  it('opens on ArrowDown while closed instead of navigating', () => {
    const { input } = renderCombobox();
    fireEvent.keyDown(input, { key: 'ArrowDown' });
    expect(screen.getByRole('listbox')).toBeInTheDocument();
  });

  it('closes on Escape and on blur', () => {
    const { input } = renderCombobox();
    fireEvent.focus(input);
    expect(screen.getByRole('listbox')).toBeInTheDocument();
    fireEvent.keyDown(input, { key: 'Escape' });
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();

    fireEvent.focus(input);
    fireEvent.blur(input);
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
  });

  it('shows a no-matches status outside the listbox and collapses aria-expanded', () => {
    const { input } = renderCombobox();
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: 'zzz' } });

    expect(screen.getByRole('status')).toHaveTextContent('No matches');
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    expect(input).toHaveAttribute('aria-expanded', 'false');
  });
});
