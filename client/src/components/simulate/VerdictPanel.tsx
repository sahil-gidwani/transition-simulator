import Badge from '../ui/Badge';
import Chip from '../ui/Chip';
import { formatDate, formatEuroCompact, formatRange, formatSignedPct } from '../../lib/format';
import { tierLabel } from '../../lib/labels';
import { useHealth } from '../../lib/queries';
import type { Prediction, SimulationResponse } from '../../lib/types';
import { CONFIDENCE_COPY } from './confidenceCopy';

// Matches the server's narrative thresholds (DIRECTION_UP / DIRECTION_DOWN).
const DIRECTION_UP = 1.05;
const DIRECTION_DOWN = 0.95;

function FreshnessNote() {
  const { data } = useHealth();
  if (!data) return null;
  return <> Values as of {formatDate(data.data.max_valuation_date)}.</>;
}

interface VerdictPanelProps {
  result: SimulationResponse;
  prediction: Prediction;
}

export default function VerdictPanel({ result, prediction }: VerdictPanelProps) {
  const confidence = CONFIDENCE_COPY[result.confidence];
  const direction =
    prediction.mid_multiplier >= DIRECTION_UP
      ? { arrow: '↑', color: 'text-rise-400', label: 'rises' }
      : prediction.mid_multiplier <= DIRECTION_DOWN
        ? { arrow: '↓', color: 'text-decline-400', label: 'falls' }
        : { arrow: '→', color: 'text-ink-400', label: 'holds' };

  const destinationLabel = result.destination.club_name ?? result.destination.league_name;

  return (
    <section className="rounded-2xl border border-pitch-800 bg-pitch-900 p-6 sm:p-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="flex flex-wrap items-center gap-2 text-sm text-ink-400">
          <span>
            If <span className="font-medium text-ink-100">{result.player.name}</span> moves to{' '}
            <span className="font-medium text-ink-100">{destinationLabel}</span>
          </span>
          <Badge>{tierLabel(result.destination.tier)}</Badge>
        </p>
        <Chip tone={confidence.tone} title={confidence.note}>
          {confidence.label}
        </Chip>
      </div>

      <div className="mt-5 flex items-baseline gap-4">
        <span aria-hidden="true" className={`text-5xl ${direction.color}`}>
          {direction.arrow}
        </span>
        <span className="text-6xl font-semibold tracking-tight text-ink-100 tabular-nums sm:text-7xl">
          {formatRange(prediction.low_eur, prediction.high_eur)}
        </span>
      </div>
      <p className="mt-3 text-ink-400">
        within {prediction.horizon_months} months · mid{' '}
        <span className="text-ink-100 tabular-nums">{formatEuroCompact(prediction.mid_eur)}</span>{' '}
        <span className={`tabular-nums ${direction.color}`}>
          ({formatSignedPct(prediction.mid_multiplier - 1)})
        </span>
      </p>

      <p className="mt-1 text-sm text-ink-400">
        Now:{' '}
        <span className="text-ink-100 tabular-nums">
          {formatEuroCompact(result.player.market_value_eur)}
        </span>
        {result.player.market_value_asof
          ? ` · as of ${formatDate(result.player.market_value_asof)}`
          : ''}
      </p>

      <p className="mt-4 max-w-xl text-sm text-ink-400/80">{confidence.note}</p>

      <footer className="mt-6 border-t border-pitch-800 pt-3 text-xs text-ink-400/70">
        Range = the middle half of outcomes across {result.pool_quality.pool_size} comparable moves,
        weighted by similarity.
        <FreshnessNote />
      </footer>
    </section>
  );
}
