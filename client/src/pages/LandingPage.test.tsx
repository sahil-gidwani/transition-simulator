import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import LandingPage from './LandingPage';

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <LandingPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('LandingPage', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify({ status: 'ok', version: '0.1.0' }))),
    );
  });

  it('renders the product name', () => {
    renderPage();
    expect(screen.getByRole('heading', { name: 'Precedent' })).toBeInTheDocument();
  });

  it('shows the API status once the health check resolves', async () => {
    renderPage();
    expect(await screen.findByText('API ok · v0.1.0')).toBeInTheDocument();
  });
});
