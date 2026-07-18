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
    note: 'Strong agreement — many closely similar moves point the same way. Not a guarantee.',
  },
  medium: {
    label: 'Medium confidence',
    tone: 'neutral',
    note: 'Reasonable evidence — a solid set of similar moves, but they disagree more.',
  },
  low: {
    label: 'Low confidence',
    tone: 'caution',
    note: 'Weak evidence — only a few similar moves, or they point in very different directions. Treat the range as a rough guide.',
  },
  insufficient: {
    label: 'Insufficient precedent',
    tone: 'decline',
    note: 'Fewer than two comparable moves on record — no honest range can be given.',
  },
};
