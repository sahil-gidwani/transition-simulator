import { m } from 'motion/react';
import { Link, Outlet, useLocation } from 'react-router';
import { formatDate } from '../../lib/format';
import { pageEnter } from '../../lib/motion';
import { useHealth } from '../../lib/queries';
import ErrorBoundary from './ErrorBoundary';
import Logo from './Logo';

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
    <div className="mesh-hero relative flex min-h-screen flex-col text-ink-100">
      <div aria-hidden="true" className="noise-overlay pointer-events-none fixed inset-0 z-50" />
      <header className="sticky top-0 z-40 border-b border-white/10 bg-pitch-950/70 backdrop-blur-md">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-3.5">
          <Link
            to="/"
            className="rounded text-ink-100 transition-colors duration-150 hover:text-tangerine-200"
          >
            <Logo />
          </Link>
          <span className="text-xs tracking-[0.25em] text-ink-500 uppercase max-sm:hidden">
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
      <footer className="border-t border-pitch-800/70">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-1 px-6 py-4 text-xs text-ink-500 sm:flex-row sm:items-center sm:justify-between">
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
