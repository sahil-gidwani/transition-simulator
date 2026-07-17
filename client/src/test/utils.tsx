import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react';
import type { ReactElement, ReactNode } from 'react';
import { MemoryRouter } from 'react-router';

interface RenderOptions {
  initialEntries?: string[];
}

/**
 * Renders under a fresh QueryClient (no retries, so error states surface
 * immediately) and a MemoryRouter. Pass a <Routes> tree as `ui` when a test
 * needs navigation targets.
 */
export function renderWithProviders(
  ui: ReactElement,
  { initialEntries = ['/'] }: RenderOptions = {},
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={initialEntries}>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  }

  return render(ui, { wrapper: Wrapper });
}
