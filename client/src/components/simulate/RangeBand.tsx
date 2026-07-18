import { formatEuroCompact, formatRange } from '../../lib/format';
import { rangeBandLayout } from '../../lib/rangeBand';

/**
 * Graphic form of the predicted range: a neutral yale band spanning
 * low→high (the band covers outcomes — it is not a good→bad axis), a
 * tangerine midpoint tick, and the player's current value as an outlined
 * marker. Low/high label the band ends; the midpoint value is stated in
 * the copy directly above, so labels never collide on tight ranges.
 */
interface RangeBandProps {
  low: number;
  mid: number;
  high: number;
  now: number;
}

export default function RangeBand({ low, mid, high, now }: RangeBandProps) {
  const layout = rangeBandLayout({ low, mid, high, now });

  return (
    <div
      role="img"
      aria-label={`Predicted range ${formatRange(low, high)} with midpoint ${formatEuroCompact(
        mid,
      )}; current value ${formatEuroCompact(now)}`}
    >
      {/* Now caption */}
      <div className="relative h-5 text-xs text-ink-400">
        <span
          className="absolute -translate-x-1/2 whitespace-nowrap"
          style={{ left: `${layout.nowPct}%` }}
        >
          now {formatEuroCompact(now)}
        </span>
      </div>

      {/* Track */}
      <div className="relative h-2.5">
        <div className="absolute inset-0 rounded-full bg-pitch-800" />
        <div
          className="absolute inset-y-0 rounded-full bg-gradient-to-r from-yale-500 to-yale-300"
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

      {/* Band-end labels */}
      <div className="relative mt-2 h-5 text-xs text-ink-400 tabular-nums">
        <span
          className="absolute -translate-x-1/2 whitespace-nowrap"
          style={{ left: `${layout.lowPct}%` }}
        >
          {formatEuroCompact(low)}
        </span>
        <span
          className="absolute -translate-x-1/2 whitespace-nowrap"
          style={{ left: `${layout.highPct}%` }}
        >
          {formatEuroCompact(high)}
        </span>
      </div>
    </div>
  );
}
