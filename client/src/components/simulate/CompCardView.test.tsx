import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../test/utils';
import type { CompCard } from '../../lib/types';
import CompCardView from './CompCardView';

function comp(overrides: Partial<CompCard>): CompCard {
  return {
    player_id: 100,
    player_name: 'Test Mover',
    season: 2023,
    transfer_date: '2023-07-01',
    age_at_transfer: 26.4,
    from_club: 'Old Club',
    to_club: 'New Club',
    from_league: 'AA1',
    to_league: 'BB1',
    v_before_eur: 10_000_000,
    v_after_eur: 7_000_000,
    multiplier: 0.7,
    delta_pct: -0.3,
    similarity: 0.83,
    tags: ['similar market value', 'recent move'],
    ...overrides,
  };
}

describe('CompCardView', () => {
  it('renders a decliner honestly: red delta, downward slope, full prominence', () => {
    renderWithProviders(<CompCardView comp={comp({})} />);

    const delta = screen.getByText('−30%');
    expect(delta).toHaveClass('text-decline-400');
    expect(screen.getByRole('img')).toHaveAttribute('data-trend', 'decline');
    expect(screen.getByRole('img')).toHaveAccessibleName('Value €10M to €7M, −30%');
    expect(screen.getByText('€10M → €7M')).toBeInTheDocument();
  });

  it('renders a riser with the rise tone', () => {
    renderWithProviders(
      <CompCardView
        comp={comp({ v_before_eur: 9_000_000, v_after_eur: 12_600_000, delta_pct: 0.4 })}
      />,
    );

    expect(screen.getByText('+40%')).toHaveClass('text-rise-400');
    expect(screen.getByRole('img')).toHaveAttribute('data-trend', 'rise');
  });

  it('renders an unchanged value as neutral', () => {
    renderWithProviders(<CompCardView comp={comp({ v_after_eur: 10_000_000, delta_pct: 0 })} />);

    expect(screen.getByText('0%')).toHaveClass('text-ink-400');
    expect(screen.getByRole('img')).toHaveAttribute('data-trend', 'flat');
  });

  it('shows the move, season, age and why-this-comp tags', () => {
    renderWithProviders(
      <CompCardView comp={comp({})} leagueNames={new Map([['BB1', 'Beta League']])} />,
    );

    expect(screen.getByText('Old Club')).toBeInTheDocument();
    expect(screen.getByText('New Club')).toBeInTheDocument();
    expect(screen.getByText(/2023\/24 · age 26 at move/)).toBeInTheDocument();
    expect(screen.getByText('similar market value')).toBeInTheDocument();
    expect(screen.getByText('recent move')).toBeInTheDocument();
    // Known league ids map to names; unknown ones fall back to the raw code.
    expect(screen.getByText('Beta League')).toBeInTheDocument();
    expect(screen.getByText('AA1')).toBeInTheDocument();
  });

  it('omits the origin badge when from_league is null (out-of-scope origin)', () => {
    renderWithProviders(
      <CompCardView
        comp={comp({ from_league: null })}
        leagueNames={new Map([['BB1', 'Beta League']])}
      />,
    );

    expect(screen.getByText('Beta League')).toBeInTheDocument();
    expect(screen.queryByText('AA1')).not.toBeInTheDocument();
    expect(screen.getByText('Old Club')).toBeInTheDocument();
  });

  it('links the comp to its player profile', () => {
    renderWithProviders(<CompCardView comp={comp({})} />);

    expect(screen.getByRole('link', { name: 'Test Mover' })).toHaveAttribute(
      'href',
      '/players/100',
    );
  });
});
