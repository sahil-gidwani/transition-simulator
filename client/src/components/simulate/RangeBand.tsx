import type { CSSProperties } from 'react';
import { formatEuroCompact, formatRange } from '../../lib/format';
import { outcomeDots, rangeBandLayout } from '../../lib/rangeBand';
import type { Trend } from '../../lib/trend';

/**
 * Graphic form of the predicted range: a neutral yale band spanning
 * low→high (the band covers outcomes — it is not a good→bad axis), a
 * tangerine midpoint tick, and the player's current value as an outlined
 * marker. Low/high label the band ends; the midpoint value is stated in
 * the copy directly above, so labels never collide on tight ranges.
 * Below the track, one dot per comp shows that move's implied outcome for
 * this player — the range visibly IS these players.
 */
export interface RangeBandOutcome {
  value: number;
  trend: Trend;
}

interface RangeBandProps {
  low: number;
  mid: number;
  high: number;
  now: number;
  outcomes?: RangeBandOutcome[];
}

const DOT_COLOR: Record<Trend, string> = {
  rise: 'bg-rise-400',
  decline: 'bg-decline-400',
  flat: 'bg-ink-400',
};

/**
 * Near the track edges a centered label would hang outside the container
 * (and widen the page on small screens), so edge labels snap to the side.
 */
function labelStyle(pct: number): CSSProperties {
  if (pct < 12) return { left: 0 };
  if (pct > 88) return { right: 0 };
  return { left: `${pct}%`, transform: 'translateX(-50%)' };
}

export default function RangeBand({ low, mid, high, now, outcomes = [] }: RangeBandProps) {
  const layout = rangeBandLayout({ low, mid, high, now });
  const dots = outcomeDots(
    { low, mid, high, now },
    outcomes.map((outcome) => outcome.value),
  );
  const beyondScale = dots.filter((dot) => dot.clamped).length;

  return (
    <div
      role="img"
      aria-label={`Predicted range ${formatRange(low, high)} with midpoint ${formatEuroCompact(
        mid,
      )}; current value ${formatEuroCompact(now)}${
        outcomes.length > 0 ? `; ${outcomes.length} comparable outcomes shown as dots` : ''
      }`}
    >
      {/* Now caption */}
      <div className="relative h-5 text-xs text-ink-400">
        <span className="absolute whitespace-nowrap" style={labelStyle(layout.nowPct)}>
          now {formatEuroCompact(now)}
        </span>
      </div>

      {/* Track */}
      <div className="relative h-2.5">
        <div className="absolute inset-0 rounded-full bg-pitch-800" />
        <div
          className="absolute inset-y-0 rounded-full bg-linear-to-r from-yale-500 to-yale-300"
          style={{ left: `${layout.lowPct}%`, width: `${layout.highPct - layout.lowPct}%` }}
        />
        {/* Midpoint tick */}
        <div
          className="absolute top-1/2 h-5 w-0.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-tangerine-300"
          style={{ left: `${layout.midPct}%` }}
        />
        {/* Now marker */}
        <div
          className="absolute top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-ink-200 bg-pitch-950"
          style={{ left: `${layout.nowPct}%` }}
        />
      </div>

      {/* Comp-outcome dots: each comp's multiplier applied to this player's
          current value. Outliers beyond the padded domain pin to the edge
          at half opacity — never disguised as data at the edge. */}
      {outcomes.length > 0 ? (
        <div data-testid="outcome-dots" className="relative mt-1.5 h-2">
          {dots.map((dot, index) => (
            <span
              key={index}
              className={`absolute top-1/2 h-1.5 w-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full ${
                DOT_COLOR[outcomes[index].trend]
              } ${dot.clamped ? 'opacity-40' : 'opacity-80'}`}
              style={{ left: `${dot.pct}%` }}
            />
          ))}
        </div>
      ) : null}

      {/* Band-end labels; a band too narrow for two labels gets one merged
          range label instead of superimposed text. */}
      <div className="relative mt-2 h-5 text-xs text-ink-400 tabular-nums">
        {layout.highPct - layout.lowPct < 14 ? (
          <span
            className="absolute whitespace-nowrap"
            style={labelStyle((layout.lowPct + layout.highPct) / 2)}
          >
            {formatRange(low, high)}
          </span>
        ) : (
          <>
            <span className="absolute whitespace-nowrap" style={labelStyle(layout.lowPct)}>
              {formatEuroCompact(low)}
            </span>
            <span className="absolute whitespace-nowrap" style={labelStyle(layout.highPct)}>
              {formatEuroCompact(high)}
            </span>
          </>
        )}
      </div>

      {outcomes.length > 0 ? (
        <p className="mt-1 text-center text-[11px] text-ink-500">
          each dot: one comparable move&apos;s implied outcome for this player
          {beyondScale > 0 ? ` (${beyondScale} beyond this scale, pinned to the edge)` : ''}
        </p>
      ) : null}
    </div>
  );
}
