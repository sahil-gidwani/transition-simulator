import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router';
import PageLayout from './components/layout/PageLayout';
import './index.css';
import { ApiError } from './lib/api';
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
    </QueryClientProvider>
  </StrictMode>,
);
