import Badge from '../ui/Badge';
import Chip from '../ui/Chip';
import { ArrowDownRight, ArrowFlat, ArrowUpRight, Clock, SealCheck } from '../ui/icons';
import { CountUpRange } from '../motion/CountUp';
import { formatDate, formatEuroCompact, formatRange, formatSignedPct } from '../../lib/format';
import { tierLabel } from '../../lib/labels';
import { useHealth } from '../../lib/queries';
import type { Prediction, SimulationResponse } from '../../lib/types';
import { CONFIDENCE_COPY } from './confidenceCopy';
import RangeBand from './RangeBand';

// Mirrors the server's narrative thresholds (constants.DIRECTION_UP/DOWN).
// COUPLING: a server retune of those constants must update these, or the
// arrow can contradict the scout's read rendered beside it. The clean fix
// is a served `direction` field — noted as a follow-up, not invented here.
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
      ? { Icon: ArrowUpRight, color: 'text-rise-400', label: 'rises' }
      : prediction.mid_multiplier <= DIRECTION_DOWN
        ? { Icon: ArrowDownRight, color: 'text-decline-400', label: 'falls' }
        : { Icon: ArrowFlat, color: 'text-ink-400', label: 'holds' };

  const destinationLabel = result.destination.club_name ?? result.destination.league_name;
  const now = result.player.market_value_eur;

  return (
    <section className="glass-panel rounded-2xl p-6 shadow-2xl shadow-yale-900/40 sm:p-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="flex flex-wrap items-center gap-2 text-sm text-ink-400">
          <span>
            If <span className="font-medium text-ink-100">{result.player.name}</span> moves to{' '}
            <span className="font-medium text-ink-100">{destinationLabel}</span>
          </span>
          <Badge title="League strength: tiers 1–4, from squad values">
            {tierLabel(result.destination.tier)}
          </Badge>
        </p>
        <Chip tone={confidence.tone} title={confidence.note} icon={<SealCheck />} elevated>
          {confidence.label}
        </Chip>
      </div>

      <div className="mt-7 text-center">
        <div className="flex items-center justify-center gap-3">
          <span aria-hidden="true" className={direction.color}>
            <direction.Icon className="h-8 w-8 sm:h-10 sm:w-10" />
          </span>
          <span className="sr-only">{`Value ${direction.label}:`}</span>
          <CountUpRange
            low={prediction.low_eur}
            high={prediction.high_eur}
            from={now}
            format={formatRange}
            className="font-display text-6xl font-medium tracking-tight text-ink-100 tabular-nums sm:text-7xl"
          />
        </div>
        <p className="mt-3 text-ink-400">
          within {prediction.horizon_months} months · midpoint{' '}
          <span className="text-ink-100 tabular-nums">{formatEuroCompact(prediction.mid_eur)}</span>{' '}
          <span className={`tabular-nums ${direction.color}`}>
            ({formatSignedPct(prediction.mid_multiplier - 1)})
          </span>
        </p>
      </div>

      <div className="mx-auto mt-6 max-w-xl">
        <RangeBand
          low={prediction.low_eur}
          mid={prediction.mid_eur}
          high={prediction.high_eur}
          now={now ?? prediction.mid_eur}
        />
      </div>

      <p className="mt-5 flex items-center justify-center gap-1.5 text-sm text-ink-400">
        <Clock className="h-3 w-3" />
        Now: <span className="text-ink-100 tabular-nums">{formatEuroCompact(now)}</span>
        {result.player.market_value_asof ? (
          <span className="text-ink-500">
            · as of {formatDate(result.player.market_value_asof)}
          </span>
        ) : null}
      </p>

      <p className="mx-auto mt-4 max-w-xl text-center text-sm text-ink-500">{confidence.note}</p>

      <footer className="mt-6 border-t border-pitch-800 pt-3 text-xs text-ink-400">
        This range covers the middle half of what happened to the {result.pool_quality.pool_size}{' '}
        most comparable players — closer matches count for more.
        <FreshnessNote />
      </footer>
    </section>
  );
}
