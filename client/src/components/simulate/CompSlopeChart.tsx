import { useId } from 'react';
import { formatEuroCompact, formatSignedPct } from '../../lib/format';
import type { CompCard } from '../../lib/types';

const W = 132;
const H = 44;
const PAD_X = 9;
const PAD_Y = 9;

const TREND_COLOR = {
  rise: 'var(--color-rise-400)',
  decline: 'var(--color-decline-400)',
  flat: 'var(--color-ink-400)',
} as const;

type Trend = keyof typeof TREND_COLOR;

function compTrend(deltaPct: number): Trend {
  if (deltaPct > 0) return 'rise';
  if (deltaPct < 0) return 'decline';
  return 'flat';
}

interface CompSlopeChartProps {
  comp: CompCard;
}

/**
 * Two-point before/after slope in plain SVG (a full chart library per card
 * would be waste at up to 47 instances). Color is never the only signal:
 * the slope itself, the signed delta text and data-trend carry it too. The
 * open origin dot and the filled, haloed destination dot repeat the
 * direction without relying on hue.
 */
export default function CompSlopeChart({ comp }: CompSlopeChartProps) {
  const trend = compTrend(comp.delta_pct);
  const color = TREND_COLOR[trend];
  const gradientId = useId();

  const lo = Math.min(comp.v_before_eur, comp.v_after_eur);
  const hi = Math.max(comp.v_before_eur, comp.v_after_eur);
  const y = (value: number) =>
    hi === lo ? H / 2 : PAD_Y + (1 - (value - lo) / (hi - lo)) * (H - 2 * PAD_Y);

  const y1 = y(comp.v_before_eur);
  const y2 = y(comp.v_after_eur);

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      width={W}
      height={H}
      role="img"
      aria-label={`Value ${formatEuroCompact(comp.v_before_eur)} to ${formatEuroCompact(
        comp.v_after_eur,
      )}, ${formatSignedPct(comp.delta_pct)}`}
      data-trend={trend}
      className="shrink-0"
    >
      <defs>
        {/* userSpaceOnUse: an objectBoundingBox gradient is never painted on a
            zero-height bbox, which a flat (held-value) comp's horizontal line is. */}
        <linearGradient
          id={gradientId}
          gradientUnits="userSpaceOnUse"
          x1={PAD_X}
          y1="0"
          x2={W - PAD_X}
          y2="0"
        >
          <stop offset="0%" stopColor={color} stopOpacity={0.45} />
          <stop offset="100%" stopColor={color} stopOpacity={1} />
        </linearGradient>
      </defs>
      <line
        x1={PAD_X}
        y1={y1}
        x2={W - PAD_X}
        y2={y2}
        stroke={`url(#${gradientId})`}
        strokeWidth={2}
        strokeLinecap="round"
      />
      {/* Origin: open dot. Destination: filled dot with a soft halo. */}
      <circle
        cx={PAD_X}
        cy={y1}
        r={3.2}
        fill="var(--color-pitch-950)"
        stroke={color}
        strokeWidth={1.6}
      />
      <circle cx={W - PAD_X} cy={y2} r={7.5} fill={color} opacity={0.18} />
      <circle cx={W - PAD_X} cy={y2} r={4} fill={color} />
    </svg>
  );
}
