import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import Logo from './Logo';

describe('Logo', () => {
  it('lockup renders the wordmark text with a decorative mark', () => {
    const { container } = render(<Logo />);
    expect(screen.getByText('PRECEDENT')).toBeInTheDocument();
    const svg = container.querySelector('svg');
    expect(svg).toHaveAttribute('aria-hidden', 'true');
  });

  it('mark-only variant carries the accessible name itself', () => {
    render(<Logo variant="mark" />);
    expect(screen.getByRole('img', { name: 'Precedent' })).toBeInTheDocument();
  });
});
