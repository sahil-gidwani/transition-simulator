import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { PoolQuality } from '../../lib/types';
import PoolQualityBanner from './PoolQualityBanner';

function poolQuality(overrides: Partial<PoolQuality>): PoolQuality {
  return {
    pool_size: 12,
    relaxation_level: 0,
    relaxation_steps: [],
    expanded_search: false,
    club_selected: false,
    elo_pool_coverage: 0.5,
    dest_elo_available: false,
    missing_age: false,
    missing_minutes: false,
    origin_tier_unknown: false,
    club_indistinct: false,
    club_standing_support: null,
    ...overrides,
  };
}

describe('PoolQualityBanner', () => {
  it('renders nothing for a clean pool', () => {
    const { container } = render(<PoolQualityBanner poolQuality={poolQuality({})} />);
    expect(container.firstChild).toBeNull();
  });

  it('lists the relaxation steps, humanized, under the expanded-search banner', () => {
    render(
      <PoolQualityBanner
        poolQuality={poolQuality({
          expanded_search: true,
          relaxation_level: 2,
          relaxation_steps: ['age band widened to +/-6 years', 'value bracket widened to 0.25-4x'],
        })}
      />,
    );

    expect(screen.getByText('We widened the search')).toBeInTheDocument();
    expect(screen.getByText('included players up to 6 years older or younger')).toBeInTheDocument();
    expect(
      screen.getByText("included players valued from 0.25× to 4× this player's value"),
    ).toBeInTheDocument();
    // The server's exact wording stays reachable as a tooltip breadcrumb.
    expect(screen.getByTitle('age band widened to +/-6 years')).toBeInTheDocument();
  });

  it('says when the club choice cannot be distinguished from the league', () => {
    render(
      <PoolQualityBanner
        poolQuality={poolQuality({
          club_selected: true,
          club_indistinct: true,
          club_standing_support: 5,
        })}
      />,
    );
    expect(
      screen.getByText(
        'The club choice barely moves the league-level answer: outcomes among these moves hardly varied with club standing.',
      ),
    ).toBeInTheDocument();
  });

  it('says when no precedent exists at the chosen club standing, even if the answer moved', () => {
    render(
      <PoolQualityBanner
        poolQuality={poolQuality({
          club_selected: true,
          club_indistinct: false,
          club_standing_support: 0,
        })}
      />,
    );
    expect(
      screen.getByText(
        'No comparable move went to a club of this standing in its league — the range reflects the league more than the club.',
      ),
    ).toBeInTheDocument();
  });

  it('lets the unsupported-standing caveat subsume the indistinct one', () => {
    render(
      <PoolQualityBanner
        poolQuality={poolQuality({
          club_selected: true,
          club_indistinct: true,
          club_standing_support: 0,
        })}
      />,
    );
    expect(screen.getByText(/No comparable move went to a club/)).toBeInTheDocument();
    expect(screen.queryByText(/barely moves the league-level answer/)).not.toBeInTheDocument();
  });

  it('passes unknown relaxation steps through verbatim', () => {
    render(
      <PoolQualityBanner
        poolQuality={poolQuality({
          expanded_search: true,
          relaxation_level: 1,
          relaxation_steps: ['minutes filter loosened to 10%'],
        })}
      />,
    );
    expect(screen.getByText('minutes filter loosened to 10%')).toBeInTheDocument();
  });

  it('shows the Elo fallback note when a club was selected without a rating', () => {
    render(
      <PoolQualityBanner
        poolQuality={poolQuality({ club_selected: true, dest_elo_available: false })}
      />,
    );

    expect(screen.getByText(/squad value stood in for club strength/i)).toBeInTheDocument();
    expect(screen.queryByText('We widened the search')).not.toBeInTheDocument();
  });

  it('does not show the Elo note when no club was selected', () => {
    const { container } = render(
      <PoolQualityBanner
        poolQuality={poolQuality({ club_selected: false, dest_elo_available: false })}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it('says when an Elo-rated club was compared against a mostly Elo-less pool', () => {
    render(
      <PoolQualityBanner
        poolQuality={poolQuality({
          club_selected: true,
          dest_elo_available: true,
          elo_pool_coverage: 0.1,
        })}
      />,
    );

    expect(screen.getByText(/what we couldn't match/i)).toBeInTheDocument();
    expect(
      screen.getByText(/only 10% of these moves have club-strength \(elo\) ratings/i),
    ).toBeInTheDocument();
  });

  it('stays quiet about Elo coverage when most of the pool carries a rating', () => {
    const { container } = render(
      <PoolQualityBanner
        poolQuality={poolQuality({
          club_selected: true,
          dest_elo_available: true,
          elo_pool_coverage: 0.8,
        })}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it('leaves low Elo coverage to the fallback note when the club itself has no rating', () => {
    render(
      <PoolQualityBanner
        poolQuality={poolQuality({
          club_selected: true,
          dest_elo_available: false,
          elo_pool_coverage: 0.1,
        })}
      />,
    );

    expect(screen.getByText(/squad value stood in for club strength/i)).toBeInTheDocument();
    expect(screen.queryByText(/carried the rest/i)).not.toBeInTheDocument();
  });

  it('does not raise the Elo-coverage caveat for league-only simulations', () => {
    const { container } = render(
      <PoolQualityBanner
        poolQuality={poolQuality({
          club_selected: false,
          dest_elo_available: false,
          elo_pool_coverage: 0,
        })}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it('surfaces query-side similarity degradations (stated-similarity principle)', () => {
    render(
      <PoolQualityBanner poolQuality={poolQuality({ missing_age: true, missing_minutes: true })} />,
    );

    expect(screen.getByText(/what we couldn't match/i)).toBeInTheDocument();
    expect(
      screen.getByText(/age is unknown, so the matches aren't age-checked/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/playing time before the move is unknown/i)).toBeInTheDocument();
    expect(screen.queryByText('We widened the search')).not.toBeInTheDocument();
  });
});
