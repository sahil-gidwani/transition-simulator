import { Line, LineChart, ResponsiveContainer, Tooltip } from 'recharts';
import { formatDate, formatEuroCompact } from '../../lib/format';
import type { ValuePoint } from '../../lib/types';

interface ValueSparklineProps {
  history: ValuePoint[];
}

/** Compact market-value history line; renders nothing with fewer than 2 points. */
export default function ValueSparkline({ history }: ValueSparklineProps) {
  if (history.length < 2) return null;

  return (
    <div className="h-14 w-56" role="img" aria-label="Market value history">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={history} margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
          <Line
            type="monotone"
            dataKey="value_eur"
            stroke="var(--color-yale-300)"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
          <Tooltip
            cursor={{ stroke: 'var(--color-pitch-800)' }}
            content={({ active, payload }) => {
              const point =
                active && payload && payload.length > 0
                  ? (payload[0]?.payload as ValuePoint | undefined)
                  : undefined;
              if (!point) return null;
              return (
                <div className="rounded border border-pitch-800 bg-pitch-900 px-2 py-1 text-xs shadow">
                  <span className="font-medium text-ink-100 tabular-nums">
                    {formatEuroCompact(point.value_eur)}
                  </span>
                  <span className="ml-2 text-ink-400">{formatDate(point.date)}</span>
                </div>
              );
            }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
