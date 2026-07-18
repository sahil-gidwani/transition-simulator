import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { MetricPercentile, PercentilesResponse } from '../../lib/types';
import PercentileBars from './PercentileBars';

function metric(overrides: Partial<MetricPercentile>): MetricPercentile {
  return {
    metric: 'goals_p90',
    label: 'Goals / 90',
    value: 0.61,
    percentile: 80,
    direction: 'higher_better',
    peer_n: 40,
    ...overrides,
  };
}

function response(overrides: Partial<PercentilesResponse>): PercentilesResponse {
  return {
    player_id: 1,
    has_stats: true,
    season: 2025,
    league_id: 'GB1',
    minutes: 2700,
    games_played: 30,
    below_floor: false,
    metrics: [metric({})],
    ...overrides,
  };
}

describe('PercentileBars', () => {
  it('renders served percentiles as-is for lower_better metrics (never re-inverts)', () => {
    render(
      <PercentileBars
        percentiles={response({
          metrics: [
            metric({
              metric: 'cards_p90',
              label: 'Cards / 90',
              direction: 'lower_better',
              percentile: 80,
              value: 0.1,
            }),
          ],
        })}
      />,
    );

    // The server already flipped bad-is-high metrics; 80 must render as 80th.
    expect(screen.getByTestId('percentile-fill-cards_p90')).toHaveStyle({ width: '80%' });
    expect(screen.getByText('80th')).toBeInTheDocument();
    expect(screen.getByText(/lower is better/i)).toBeInTheDocument();
  });

  it('shows value and peer context but withholds the bar when the percentile is null', () => {
    render(
      <PercentileBars
        percentiles={response({
          below_floor: true,
          metrics: [metric({ percentile: null, value: 0.42 })],
        })}
      />,
    );

    expect(screen.getByText(/too few minutes this season for a fair ranking/i)).toBeInTheDocument();
    expect(screen.getByText('0.42')).toBeInTheDocument();
    expect(screen.getByText(/not ranked — too few minutes/i)).toBeInTheDocument();
    expect(screen.queryByTestId('percentile-fill-goals_p90')).not.toBeInTheDocument();
    expect(screen.getByText(/against 40 players in the same position/i)).toBeInTheDocument();
  });

  it('renders the clean-sheet rate as a percentage', () => {
    render(
      <PercentileBars
        percentiles={response({
          metrics: [
            metric({
              metric: 'clean_sheet_rate',
              label: 'Clean-sheet rate',
              value: 0.35,
              percentile: 64,
            }),
          ],
        })}
      />,
    );

    expect(screen.getByText('35%')).toBeInTheDocument();
  });

  it('attributes the peer group to the stats-season league when provided', () => {
    render(<PercentileBars percentiles={response({})} leagueLabel="Premier League" />);

    expect(
      screen.getByText(/against 40 players in the same position in Premier League/i),
    ).toBeInTheDocument();
  });

  it('shows the empty state when the player has no stats', () => {
    render(<PercentileBars percentiles={response({ has_stats: false, metrics: [] })} />);

    expect(screen.getByText(/no league appearance data/i)).toBeInTheDocument();
  });
});
