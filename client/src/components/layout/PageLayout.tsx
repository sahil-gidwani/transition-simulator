import { m } from 'motion/react';
import { Link, Outlet, useLocation } from 'react-router';
import { formatDate } from '../../lib/format';
import { pageEnter } from '../../lib/motion';
import { useHealth } from '../../lib/queries';
import ErrorBoundary from './ErrorBoundary';

function FooterFreshness() {
  const { data } = useHealth();
  if (!data) return null;
  return (
    <span className="whitespace-nowrap">
      Values as of {formatDate(data.data.max_valuation_date)}
    </span>
  );
}

export default function PageLayout() {
  const location = useLocation();
  return (
    <div className="flex min-h-screen flex-col bg-pitch-950 text-ink-100">
      <header className="border-b border-pitch-800">
        <div className="mx-auto flex w-full max-w-6xl items-baseline justify-between px-6 py-4">
          <Link
            to="/"
            className="font-display text-xl font-semibold tracking-[0.18em] text-tangerine-300"
          >
            PRECEDENT
          </Link>
          <span className="text-xs tracking-[0.3em] text-ink-400 uppercase max-sm:hidden">
            Transfer valuations
          </span>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-8">
        {/* Enter-only route transition: keyed on pathname so each page fades
            in fresh. No exit choreography — the ErrorBoundary lives inside so
            a crashed page can never strand a leaving clone. */}
        <m.div key={location.pathname} {...pageEnter}>
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </m.div>
      </main>
      <footer className="border-t border-pitch-800">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-1 px-6 py-4 text-xs text-ink-400 sm:flex-row sm:items-center sm:justify-between">
          <span>
            Player and market-value data: Transfermarkt, via the player-scores dataset · Club
            strength: ClubElo — clubelo.com
          </span>
          <FooterFreshness />
        </div>
      </footer>
    </div>
  );
}
