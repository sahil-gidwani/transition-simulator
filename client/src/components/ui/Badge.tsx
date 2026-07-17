import type { ReactNode } from 'react';

interface BadgeProps {
  children: ReactNode;
  variant?: 'neutral' | 'brass';
  title?: string;
}

/** Bordered pill for compact identity labels (position codes, leagues, tiers). */
export default function Badge({ children, variant = 'neutral', title }: BadgeProps) {
  const tone =
    variant === 'brass' ? 'border-brass-400/40 text-brass-300' : 'border-pitch-800 text-ink-400';
  return (
    <span
      title={title}
      className={`inline-flex items-center rounded border px-1.5 py-0.5 text-xs font-medium tracking-wide whitespace-nowrap ${tone}`}
    >
      {children}
    </span>
  );
}
