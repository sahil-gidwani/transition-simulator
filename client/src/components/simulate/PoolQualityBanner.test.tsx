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
    ...overrides,
  };
}

describe('PoolQualityBanner', () => {
  it('renders nothing for a clean pool', () => {
    const { container } = render(<PoolQualityBanner poolQuality={poolQuality({})} />);
    expect(container.firstChild).toBeNull();
  });

  it('lists the relaxation steps under the expanded-search banner', () => {
    render(
      <PoolQualityBanner
        poolQuality={poolQuality({
          expanded_search: true,
          relaxation_level: 2,
          relaxation_steps: ['age band widened to +/-6 years', 'value bracket widened to 0.25-4x'],
        })}
      />,
    );

    expect(screen.getByText('Expanded search')).toBeInTheDocument();
    expect(screen.getByText('age band widened to +/-6 years')).toBeInTheDocument();
    expect(screen.getByText('value bracket widened to 0.25-4x')).toBeInTheDocument();
  });

  it('shows the Elo fallback note when a club was selected without a rating', () => {
    render(
      <PoolQualityBanner
        poolQuality={poolQuality({ club_selected: true, dest_elo_available: false })}
      />,
    );

    expect(screen.getByText(/squad-value tiers stood in/i)).toBeInTheDocument();
    expect(screen.queryByText('Expanded search')).not.toBeInTheDocument();
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

    expect(screen.getByText('Similarity caveats')).toBeInTheDocument();
    expect(
      screen.getByText(/available for only 10% of these comparable moves/i),
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

    expect(screen.getByText(/squad-value tiers stood in/i)).toBeInTheDocument();
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

    expect(screen.getByText('Similarity caveats')).toBeInTheDocument();
    expect(screen.getByText(/age unknown — comps were not age-matched/i)).toBeInTheDocument();
    expect(screen.getByText(/playing time unknown/i)).toBeInTheDocument();
    expect(screen.queryByText('Expanded search')).not.toBeInTheDocument();
  });
});
