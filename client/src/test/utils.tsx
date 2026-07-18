import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react';
import { domAnimation, LazyMotion, MotionConfig } from 'motion/react';
import type { ReactElement, ReactNode } from 'react';
import { MemoryRouter } from 'react-router';
import { CompareProvider } from '../lib/compare';

interface RenderOptions {
  initialEntries?: string[];
}

/**
 * Renders under a fresh QueryClient (no retries, so error states surface
 * immediately), a MemoryRouter, and the app's motion providers (LazyMotion is
 * strict, so m.* components need it in tests too). Pass a <Routes> tree as
 * `ui` when a test needs navigation targets.
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
        <MotionConfig reducedMotion="user">
          <LazyMotion features={domAnimation} strict>
            <CompareProvider>
              <MemoryRouter initialEntries={initialEntries}>{children}</MemoryRouter>
            </CompareProvider>
          </LazyMotion>
        </MotionConfig>
      </QueryClientProvider>
    );
  }

  return render(ui, { wrapper: Wrapper });
}
