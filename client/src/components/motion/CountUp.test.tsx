import { render, screen } from '@testing-library/react';
import { StrictMode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { formatEuroCompact, formatRange } from '../../lib/format';
import { CountUp, CountUpRange } from './CountUp';

function stubMatchMedia(reducedMotion: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: query.includes('prefers-reduced-motion') ? reducedMotion : false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

/** Renders with the OS reduced-motion setting stubbed on. */
function renderReduced(ui: React.ReactElement) {
  stubMatchMedia(true);
  return render(ui);
}

afterEach(() => {
  stubMatchMedia(false);
});

describe('CountUp', () => {
  it('renders the exact formatted value statically when no `from` anchor is given', () => {
    render(<CountUp value={38_000_000} format={formatEuroCompact} />);
    expect(screen.getByText('€38M')).toBeInTheDocument();
  });

  it('settles on exactly format(value) after animating from an anchor', async () => {
    render(
      <CountUp value={38_000_000} from={22_000_000} format={formatEuroCompact} durationS={0.05} />,
    );
    expect(await screen.findByText('€38M')).toBeInTheDocument();
  });

  it('renders the final value synchronously under reduced motion', () => {
    renderReduced(
      <CountUp value={38_000_000} from={22_000_000} format={formatEuroCompact} durationS={5} />,
    );
    expect(screen.getByText('€38M')).toBeInTheDocument();
  });

  it('survives StrictMode double-mount with the exact final value', async () => {
    render(
      <StrictMode>
        <CountUp value={1_200_000} from={850_000} format={formatEuroCompact} durationS={0.05} />
      </StrictMode>,
    );
    expect(await screen.findByText('€1.2M')).toBeInTheDocument();
  });
});

describe('CountUpRange', () => {
  it('settles on exactly formatRange(low, high) including unit compression', async () => {
    render(
      <CountUpRange
        low={38_000_000}
        high={46_000_000}
        from={22_000_000}
        format={formatRange}
        durationS={0.05}
      />,
    );
    expect(await screen.findByText('€38–46M')).toBeInTheDocument();
  });

  it('renders the final range statically without an anchor', () => {
    render(<CountUpRange low={850_000} high={1_200_000} format={formatRange} />);
    expect(screen.getByText('€850k–€1.2M')).toBeInTheDocument();
  });

  it('renders the final range synchronously under reduced motion', () => {
    renderReduced(
      <CountUpRange
        low={38_000_000}
        high={46_000_000}
        from={22_000_000}
        format={formatRange}
        durationS={5}
      />,
    );
    expect(screen.getByText('€38–46M')).toBeInTheDocument();
  });
});
