import { Link } from 'react-router';
import { formatRange, formatSignedPct } from '../../lib/format';
import { useCompare } from '../../lib/compareContext';
import { midpointGap } from '../../lib/comparePins';

/**
 * The A-vs-B tray: pinned verdicts docked above the fold's bottom edge.
 * Each card links back to the exact simulate URL that produced it
 * (simulations are deterministic and cached, so the trip back is instant).
 */
export default function CompareTray() {
  const { pins, unpin, clear } = useCompare();
  if (pins.length === 0) return null;
  const gap = midpointGap(pins);

  return (
    <div className="fixed inset-x-0 bottom-0 z-40 px-4 pb-4">
      <aside
        aria-label="Compare tray"
        className="mx-auto max-w-3xl rounded-2xl border border-pitch-700 bg-pitch-950/95 p-4 shadow-2xl shadow-black/60 backdrop-blur"
      >
        <div className="flex items-center justify-between gap-3">
          <p className="text-xs font-medium tracking-[0.14em] text-ink-500 uppercase">
            Compare {pins.length === 2 ? 'A vs B' : '— pin one more scenario'}
          </p>
          <button type="button" onClick={clear} className="text-xs text-ink-400 hover:text-ink-100">
            Clear
          </button>
        </div>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {pins.map((pin) => (
            <div
              key={pin.key}
              className="flex items-start justify-between gap-3 rounded-xl border border-pitch-800 bg-pitch-900 p-3"
            >
              <div className="min-w-0">
                <Link
                  to={pin.url}
                  className="block truncate text-sm text-ink-100 hover:text-tangerine-200"
                >
                  {pin.playerName} → {pin.destinationLabel}
                </Link>
                <p className="mt-1 text-sm text-ink-400 tabular-nums">
                  {formatRange(pin.lowEur, pin.highEur)}
                  <span className="ml-2 text-xs text-ink-500">{pin.confidence} confidence</span>
                </p>
              </div>
              <button
                type="button"
                onClick={() => unpin(pin.key)}
                aria-label={`Unpin ${pin.playerName} to ${pin.destinationLabel}`}
                className="shrink-0 text-xs text-ink-500 hover:text-ink-100"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
        {gap !== null ? (
          <p className="mt-2 text-center text-xs text-ink-400">
            midpoint gap (B vs A):{' '}
            <span className="text-ink-100 tabular-nums">{formatSignedPct(gap)}</span>
          </p>
        ) : null}
      </aside>
    </div>
  );
}
