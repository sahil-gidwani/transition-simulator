import Badge from '../ui/Badge';
import Chip from '../ui/Chip';
import { AlertRing, ArrowDownRight, ArrowFlat, ArrowUpRight, Clock, SealCheck } from '../ui/icons';
import { secondaryActionCompact } from '../ui/actions';
import { CountUpRange } from '../motion/CountUp';
import { useCompare } from '../../lib/compareContext';
import { hasPin, pinKey } from '../../lib/comparePins';
import {
  formatDate,
  formatEuroCompact,
  formatRange,
  formatSignedPct,
  horizonMonthYear,
} from '../../lib/format';
import { tierLabel } from '../../lib/labels';
import { compTrend } from '../../lib/trend';
import { useHealth } from '../../lib/queries';
import type { Direction, Prediction, SimulationResponse } from '../../lib/types';
import { CONFIDENCE_COPY } from './confidenceCopy';
import RangeBand from './RangeBand';

// The verdict direction is SERVED data (the same function feeds the scout's
// read), so the arrow can never contradict the narrative across a retune.
const DIRECTION_VIEW: Record<Direction, { Icon: typeof ArrowFlat; color: string; label: string }> =
  {
    rise: { Icon: ArrowUpRight, color: 'text-rise-400', label: 'rises' },
    decline: { Icon: ArrowDownRight, color: 'text-decline-400', label: 'falls' },
    flat: { Icon: ArrowFlat, color: 'text-ink-400', label: 'holds' },
  };

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
  const direction = DIRECTION_VIEW[result.direction ?? 'flat'];
  const { pins, pin, unpin } = useCompare();

  const destinationLabel = result.destination.club_name ?? result.destination.league_name;
  const now = result.player.market_value_eur;
  const compareKey = pinKey(
    result.player.player_id,
    result.destination.league_id,
    result.destination.club_id,
  );
  const pinned = hasPin(pins, compareKey);
  const simulateUrl =
    `/players/${result.player.player_id}/simulate?league=${result.destination.league_id}` +
    (result.destination.club_id != null ? `&club=${result.destination.club_id}` : '');
  // Concrete horizon: "12 months" only means something against the value's
  // as-of date, so say which month that actually is.
  const horizonBy = horizonMonthYear(result.player.market_value_asof, prediction.horizon_months);

  return (
    <section className="glass-panel rounded-2xl p-6 shadow-2xl shadow-yale-900/40 sm:p-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="flex flex-wrap items-center gap-2 text-sm text-ink-400">
          <span>
            If <span className="font-medium text-ink-100">{result.player.name}</span> moves to{' '}
            <span className="font-medium text-ink-100">{destinationLabel}</span>
          </span>
          <Badge title="League strength band from median squad value (Elite ≈ €100M+, Strong ≈ €24M+, Emerging ≈ €12M+, Developing below)">
            {tierLabel(result.destination.tier)}
          </Badge>
        </p>
        <span className="flex items-center gap-2">
          <Chip
            tone={confidence.tone}
            title={confidence.note}
            // Weak-evidence tiers must not wear a verified-looking seal.
            icon={confidence.tone === 'caution' ? <AlertRing /> : <SealCheck />}
            elevated
          >
            {confidence.label}
          </Chip>
          <button
            type="button"
            onClick={() =>
              pinned
                ? unpin(compareKey)
                : pin({
                    key: compareKey,
                    playerName: result.player.name,
                    destinationLabel,
                    url: simulateUrl,
                    lowEur: prediction.low_eur,
                    midEur: prediction.mid_eur,
                    highEur: prediction.high_eur,
                    confidence: result.confidence,
                  })
            }
            title="Pin this verdict to compare it against another destination"
            className={secondaryActionCompact}
          >
            {pinned ? 'Pinned ✓' : 'Compare'}
          </button>
        </span>
      </div>

      <div className="mt-7 text-center">
        <div className="flex items-center justify-center gap-3">
          <span aria-hidden="true" className={direction.color}>
            <direction.Icon className="h-7 w-7 sm:h-10 sm:w-10" />
          </span>
          <span className="sr-only">{`Value ${direction.label}:`}</span>
          <CountUpRange
            low={prediction.low_eur}
            high={prediction.high_eur}
            from={now}
            format={formatRange}
            className="font-display text-4xl font-medium tracking-tight text-ink-100 tabular-nums sm:text-6xl xl:text-7xl"
          />
        </div>
        <p className="mt-3 text-ink-400">
          within {prediction.horizon_months} months{horizonBy ? ` (by ${horizonBy})` : ''} ·
          midpoint{' '}
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
          // Each comp's implied outcome for THIS player: its multiplier
          // applied to the current value — the range visibly IS the comps.
          outcomes={
            now != null
              ? result.comps.map((comp) => ({
                  value: comp.multiplier * now,
                  trend: compTrend(comp.delta_pct),
                }))
              : []
          }
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
