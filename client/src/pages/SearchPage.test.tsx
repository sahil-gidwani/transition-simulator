import { fireEvent, screen, waitFor } from '@testing-library/react';
import { Route, Routes } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '../test/utils';
import type { PlayerSearchResult } from '../lib/types';
import SearchPage from './SearchPage';

const haaland: PlayerSearchResult = {
  player_id: 418560,
  name: 'Erling Haaland',
  age: 25,
  position_group: 'ATT',
  sub_position: 'Centre-Forward',
  club_name: 'Manchester City',
  league_id: 'GB1',
  league_name: 'Premier League',
  market_value_eur: 180_000_000,
  market_value_asof: '2026-06-01',
};

function renderSearch() {
  return renderWithProviders(
    <Routes>
      <Route path="/search" element={<SearchPage />} />
      <Route path="/players/:id" element={<div>profile-route</div>} />
    </Routes>,
    { initialEntries: ['/search'] },
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('SearchPage', () => {
  it('does not fetch for queries under two characters', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    renderSearch();

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'h' } });
    await new Promise((resolve) => setTimeout(resolve, 350));

    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByText(/type at least two letters/i)).toBeInTheDocument();
  });

  it('shows debounced results and navigates with arrow keys + Enter', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve([haaland]),
    });
    vi.stubGlobal('fetch', fetchMock);
    renderSearch();

    const input = screen.getByRole('combobox');
    fireEvent.change(input, { target: { value: 'haal' } });

    const option = await screen.findByRole('option', { name: /erling haaland/i });
    expect(option).toHaveTextContent('€180M');
    expect(option).toHaveTextContent('Manchester City · Premier League');
    expect(fetchMock).toHaveBeenCalledWith('/api/players/search?q=haal', undefined);

    fireEvent.keyDown(input, { key: 'ArrowDown' });
    await waitFor(() => expect(option).toHaveAttribute('aria-selected', 'true'));
    fireEvent.keyDown(input, { key: 'Enter' });

    expect(await screen.findByText('profile-route')).toBeInTheDocument();
  });

  it('shows the empty state when nothing matches', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, status: 200, json: () => Promise.resolve([]) }),
    );
    renderSearch();

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'zzzz' } });

    expect(await screen.findByText(/no players match/i)).toBeInTheDocument();
    expect(screen.getByText(/first-tier leagues/i)).toBeInTheDocument();
  });

  it('shows an error state with a retry button when the request fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')));
    renderSearch();

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'haal' } });

    expect(await screen.findByText(/search request failed/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
  });
});
