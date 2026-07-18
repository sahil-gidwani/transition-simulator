import type { ReactNode } from 'react';

interface BadgeProps {
  children: ReactNode;
  variant?: 'neutral' | 'accent';
  title?: string;
}

/**
 * Identity family: squared, hairline-bordered labels for who/where facts
 * (position codes, leagues, tiers). States and outcomes use the round Chip;
 * the shape difference is deliberate so the two never read as one another.
 */
export default function Badge({ children, variant = 'neutral', title }: BadgeProps) {
  const tone =
    variant === 'accent'
      ? 'border-tangerine-300/40 text-tangerine-300'
      : 'border-pitch-700 text-ink-400';
  return (
    <span
      title={title}
      className={`inline-flex items-center rounded-sm border bg-pitch-900/40 px-1.5 py-0.5 text-xs font-medium tracking-wide whitespace-nowrap ${tone}`}
    >
      {children}
    </span>
  );
}
