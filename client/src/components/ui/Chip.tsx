import type { ReactNode } from 'react';

const TONES = {
  accent: 'bg-tangerine-300/15 text-tangerine-300',
  neutral: 'bg-pitch-800 text-ink-400',
  caution: 'bg-caution-400/15 text-caution-400',
  decline: 'bg-decline-400/15 text-decline-400',
  rise: 'bg-rise-400/15 text-rise-400',
} as const;

export type ChipTone = keyof typeof TONES;

interface ChipProps {
  children: ReactNode;
  tone?: ChipTone;
  title?: string;
}

/** Filled pill for states and tags (confidence, comp tags, caveats). */
export default function Chip({ children, tone = 'neutral', title }: ChipProps) {
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap ${TONES[tone]}`}
    >
      {children}
    </span>
  );
}
