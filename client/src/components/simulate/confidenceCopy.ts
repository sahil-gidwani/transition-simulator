import type { ChipTone } from '../ui/Chip';
import type { Confidence } from '../../lib/types';

interface ConfidenceCopy {
  label: string;
  tone: ChipTone;
  note: string;
}

/**
 * Honest confidence framing. The backtest found the high tier's range
 * under-covers its nominal 50% (documented open finding), so "high" is
 * presented as precedent agreement — never as a probability guarantee.
 */
export const CONFIDENCE_COPY: Record<Confidence, ConfidenceCopy> = {
  high: {
    label: 'High confidence',
    tone: 'accent',
    note: 'Strong precedent agreement — a deep pool of comparable moves points the same way. Not a probability guarantee.',
  },
  medium: {
    label: 'Medium confidence',
    tone: 'neutral',
    note: 'Reasonable precedent — the pool is solid but comps disagree more.',
  },
  low: {
    label: 'Low confidence',
    tone: 'caution',
    note: 'Weak precedent — few comps or wide disagreement. Treat the range as indicative.',
  },
  insufficient: {
    label: 'Insufficient precedent',
    tone: 'decline',
    note: 'Fewer than two comparable transitions on record — no responsible range can be given.',
  },
};
