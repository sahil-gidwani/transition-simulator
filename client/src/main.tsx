import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { domAnimation, LazyMotion, MotionConfig } from 'motion/react';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router';
import PageLayout from './components/layout/PageLayout';
import './index.css';
import { ApiError } from './lib/api';
import { CompareProvider } from './lib/compare';
import PlayerProfilePage from './pages/PlayerProfilePage';
import SearchPage from './pages/SearchPage';
import SimulatePage from './pages/SimulatePage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // The dataset is static per server build; a page refresh is the cache bust.
      staleTime: Infinity,
      refetchOnWindowFocus: false,
      // Client errors (404 unknown player, 409 no valuation) will not heal on retry.
      retry: (failureCount, error) =>
        failureCount < 2 &&
        !(error instanceof ApiError && error.status >= 400 && error.status < 500),
    },
  },
});

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      {/* reducedMotion="user": every motion component honours the OS setting.
          LazyMotion + m.* keeps the animation runtime to the ~15kB dom subset. */}
      <MotionConfig reducedMotion="user">
        <LazyMotion features={domAnimation} strict>
          <CompareProvider>
            <BrowserRouter>
              <Routes>
                <Route element={<PageLayout />}>
                  <Route path="/" element={<Navigate to="/search" replace />} />
                  <Route path="/search" element={<SearchPage />} />
                  <Route path="/players/:id" element={<PlayerProfilePage />} />
                  <Route path="/players/:id/simulate" element={<SimulatePage />} />
                </Route>
              </Routes>
            </BrowserRouter>
          </CompareProvider>
        </LazyMotion>
      </MotionConfig>
    </QueryClientProvider>
  </StrictMode>,
);
