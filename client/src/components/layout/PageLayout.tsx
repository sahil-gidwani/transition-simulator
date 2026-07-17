import { Link, Outlet } from 'react-router';
import { formatDate } from '../../lib/format';
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
  return (
    <div className="flex min-h-screen flex-col bg-pitch-950 text-ink-100">
      <header className="border-b border-pitch-800">
        <div className="mx-auto flex w-full max-w-6xl items-baseline justify-between px-6 py-4">
          <Link
            to="/"
            className="font-serif text-xl font-semibold tracking-[0.18em] text-brass-300"
          >
            PRECEDENT
          </Link>
          <span className="text-xs tracking-[0.3em] text-ink-400 uppercase max-sm:hidden">
            Transfer valuations
          </span>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-8">
        <ErrorBoundary>
          <Outlet />
        </ErrorBoundary>
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
