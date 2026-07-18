import { m } from 'motion/react';
import { Link, Outlet, useLocation } from 'react-router';
import { Search } from '../ui/icons';
import { secondaryActionCompact } from '../ui/actions';
import { pageEnter } from '../../lib/motion';
import CompareTray from './CompareTray';
import ErrorBoundary from './ErrorBoundary';
import Logo from './Logo';

const footerLink =
  'text-ink-400 underline decoration-pitch-700 underline-offset-2 transition-colors duration-150 hover:text-tangerine-200 hover:decoration-tangerine-300/60';

/** Brand hairline: a yale glint that fades out toward both edges. */
function Hairline() {
  return (
    <div
      aria-hidden="true"
      className="h-px bg-linear-to-r from-transparent via-yale-400/50 to-transparent"
    />
  );
}

/**
 * Slim route-driven breadcrumb (Search → Player → Simulate). Lives in the
 * layout so every page below the search hero gets a way back without each
 * page reinventing it; labels are generic because the layout doesn't (and
 * shouldn't) fetch the player just to render a name.
 */
function Breadcrumb({ pathname }: { pathname: string }) {
  const match = /^\/players\/([^/]+)(\/simulate)?$/.exec(pathname);
  if (!match) return null;
  const [, playerId, simulate] = match;
  const crumbLink = 'transition-colors duration-150 hover:text-tangerine-200';
  return (
    <nav aria-label="Breadcrumb" className="mb-4 text-xs text-ink-500">
      <ol className="flex items-center gap-1.5">
        <li>
          <Link to="/search" className={crumbLink}>
            Search
          </Link>
        </li>
        <li aria-hidden="true">›</li>
        <li>
          {simulate ? (
            <Link to={`/players/${playerId}`} className={crumbLink}>
              Player
            </Link>
          ) : (
            <span aria-current="page" className="text-ink-400">
              Player
            </span>
          )}
        </li>
        {simulate ? (
          <>
            <li aria-hidden="true">›</li>
            <li>
              <span aria-current="page" className="text-ink-400">
                Simulate
              </span>
            </li>
          </>
        ) : null}
      </ol>
    </nav>
  );
}

export default function PageLayout() {
  const location = useLocation();
  return (
    <div className="mesh-hero relative flex min-h-screen flex-col text-ink-100">
      <div aria-hidden="true" className="noise-overlay pointer-events-none fixed inset-0 z-50" />
      <header className="sticky top-0 z-40 bg-pitch-950/70 backdrop-blur-md">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-6 py-3.5">
          <div className="flex min-w-0 items-center gap-4">
            <Link
              to="/"
              className="rounded text-ink-100 transition-colors duration-150 hover:text-tangerine-200"
            >
              <Logo />
            </Link>
            <span aria-hidden="true" className="hidden h-4 w-px bg-pitch-700 md:block" />
            <span className="hidden text-[11px] tracking-[0.22em] text-ink-500 uppercase md:block">
              Transfer valuations
            </span>
          </div>
          <Link to="/search" className={`${secondaryActionCompact} inline-flex items-center gap-2`}>
            <Search className="h-3 w-3 text-ink-400" />
            <span className="max-sm:hidden">Search players</span>
            <span className="sm:hidden">Search</span>
          </Link>
        </div>
        <Hairline />
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-8">
        {/* Enter-only route transition: keyed on pathname so each page fades
            in fresh. No exit choreography — the ErrorBoundary lives inside so
            a crashed page can never strand a leaving clone. */}
        <m.div key={location.pathname} {...pageEnter}>
          <Breadcrumb pathname={location.pathname} />
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </m.div>
      </main>
      <CompareTray />
      <footer>
        <Hairline />
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-6 py-8 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <Logo variant="mark" decorative className="h-6 w-6 text-ink-200" />
            <p className="mt-3 text-xs leading-relaxed text-ink-500">
              Transfer valuations, backed by named precedent.
            </p>
          </div>
          <div className="text-xs leading-relaxed text-ink-500 sm:text-right">
            <p>
              Player and market-value data: Transfermarkt, via{' '}
              <a
                href="https://github.com/dcaribou/transfermarkt-datasets"
                target="_blank"
                rel="noreferrer"
                className={footerLink}
              >
                transfermarkt-datasets
              </a>{' '}
              · Club strength:{' '}
              <a href="http://clubelo.com" target="_blank" rel="noreferrer" className={footerLink}>
                ClubElo
              </a>
            </p>
            <p className="mt-1.5">Developed by Sahil Gidwani</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
