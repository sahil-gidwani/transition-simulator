import type { ReactNode } from 'react';

const TONES = {
  accent: { bg: 'bg-tangerine-300/15', text: 'text-tangerine-300' },
  neutral: { bg: 'bg-pitch-800', text: 'text-ink-400' },
  caution: { bg: 'bg-caution-400/15', text: 'text-caution-400' },
  decline: { bg: 'bg-decline-400/15', text: 'text-decline-400' },
  rise: { bg: 'bg-rise-400/15', text: 'text-rise-400' },
} as const;

export type ChipTone = keyof typeof TONES;

interface ChipProps {
  children: ReactNode;
  tone?: ChipTone;
  title?: string;
  /** Leading glyph from ui/icons — makes the state family scannable. */
  icon?: ReactNode;
  /** Hero treatment (gradient ring) for the one chip that anchors a panel. */
  elevated?: boolean;
}

/**
 * State family: round, filled pills for verdicts and conditions (confidence,
 * caveats, tags). Identity facts use the squared Badge instead.
 */
export default function Chip({ children, tone = 'neutral', title, icon, elevated }: ChipProps) {
  const toneClass = elevated
    ? `gradient-border ${TONES[tone].text}`
    : `${TONES[tone].bg} ${TONES[tone].text}`;
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap ${toneClass}`}
    >
      {icon}
      {children}
    </span>
  );
}
