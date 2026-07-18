import { useId } from 'react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { formatDate, formatEuroCompact } from '../../lib/format';
import { usePrefersReducedMotion } from '../../lib/motion';
import type { ValuePoint } from '../../lib/types';

/**
 * Full market-value history as a gradient area chart. Single series (title
 * names it — no legend), yale for magnitude, tangerine only on the hover
 * marker. Transfer markers are deliberately omitted: the profile payload
 * carries valuations only, and inventing transfer dates would violate the
 * real-data-only principle.
 */
interface MarketValueChartProps {
  history: ValuePoint[];
}

interface Datum {
  ts: number;
  date: string;
  value: number;
}

function yearTicks(data: Datum[]): number[] {
  const first = new Date(data[0]!.ts).getFullYear() + 1;
  const last = new Date(data[data.length - 1]!.ts).getFullYear();
  const years: number[] = [];
  for (let y = first; y <= last; y += 1) years.push(Date.UTC(y, 0, 1));
  // Thin to at most ~8 labels so ticks never cramp.
  const step = Math.max(1, Math.ceil(years.length / 8));
  return years.filter((_, i) => i % step === 0);
}

function ChartTooltip({ active, payload }: { active?: boolean; payload?: { payload: Datum }[] }) {
  const datum = payload?.[0]?.payload;
  if (!active || !datum) return null;
  return (
    <div className="rounded-lg border border-pitch-700 bg-pitch-850 px-3 py-2 shadow-xl shadow-black/40">
      <div className="font-semibold text-ink-100 tabular-nums">
        {formatEuroCompact(datum.value)}
      </div>
      <div className="mt-0.5 text-xs text-ink-400">{formatDate(datum.date)}</div>
    </div>
  );
}

export default function MarketValueChart({ history }: MarketValueChartProps) {
  const gradientId = useId();
  const reduced = usePrefersReducedMotion();

  const data: Datum[] = history
    .map((p) => ({ ts: Date.parse(p.date), date: p.date, value: p.value_eur }))
    .filter((d) => Number.isFinite(d.ts))
    .sort((a, b) => a.ts - b.ts);

  if (data.length < 2) {
    return (
      <p className="text-sm text-ink-500">
        Not enough valuation history to chart — the market value above is the whole record.
      </p>
    );
  }

  const first = data[0]!;
  const last = data[data.length - 1]!;

  return (
    <div
      role="img"
      aria-label={`Market value history: ${formatEuroCompact(first.value)} in ${formatDate(
        first.date,
      )} to ${formatEuroCompact(last.value)} as of ${formatDate(last.date)}, ${data.length} valuations`}
      className="h-64 w-full"
    >
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--color-yale-300)" stopOpacity={0.3} />
              <stop offset="100%" stopColor="var(--color-yale-300)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} stroke="var(--color-pitch-800)" strokeOpacity={0.6} />
          <XAxis
            dataKey="ts"
            type="number"
            scale="time"
            domain={['dataMin', 'dataMax']}
            ticks={yearTicks(data)}
            tickFormatter={(ts: number) => String(new Date(ts).getFullYear())}
            tick={{ fill: 'var(--color-ink-500)', fontSize: 12 }}
            axisLine={{ stroke: 'var(--color-pitch-800)' }}
            tickLine={false}
          />
          <YAxis
            width={52}
            domain={[0, 'auto']}
            tickCount={5}
            tickFormatter={(v: number) => formatEuroCompact(v)}
            tick={{ fill: 'var(--color-ink-500)', fontSize: 12 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip content={<ChartTooltip />} cursor={{ stroke: 'var(--color-pitch-700)' }} />
          <Area
            type="monotone"
            dataKey="value"
            stroke="var(--color-yale-300)"
            strokeWidth={2}
            fill={`url(#${gradientId})`}
            dot={
              data.length <= 40
                ? {
                    r: 2.5,
                    fill: 'var(--color-pitch-950)',
                    stroke: 'var(--color-yale-300)',
                    strokeWidth: 1.5,
                  }
                : false
            }
            activeDot={{
              r: 5,
              fill: 'var(--color-tangerine-300)',
              stroke: 'var(--color-pitch-950)',
              strokeWidth: 2,
            }}
            isAnimationActive={!reduced}
            animationDuration={700}
            animationEasing="ease-out"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
