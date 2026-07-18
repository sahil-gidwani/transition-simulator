interface MarkProps {
  className?: string;
  label?: string;
}

/**
 * The Precedent mark: a value leaves the baseline (the before-dot) on a
 * rising arc and lands higher (the tangerine after-dot) — the comp-card
 * before→after slope made iconic. Hand-authored paths; the baseline takes
 * yale, the arc and before-dot inherit currentColor, the after-dot carries
 * the accent.
 */
function Mark({ className, label }: MarkProps) {
  return (
    <svg
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      {...(label ? { role: 'img', 'aria-label': label } : { 'aria-hidden': true })}
    >
      <path
        d="M4.5 25.5H27.5"
        stroke="var(--color-yale-400)"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <circle cx="8.5" cy="25.5" r="2.6" fill="currentColor" />
      <path
        d="M8.5 25.5C15 25 20 20 23.5 11.5"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
      />
      <circle cx="24" cy="9.5" r="3.4" fill="var(--color-tangerine-300)" />
    </svg>
  );
}

interface LogoProps {
  variant?: 'lockup' | 'mark';
  className?: string;
}

export default function Logo({ variant = 'lockup', className }: LogoProps) {
  if (variant === 'mark') {
    return <Mark className={className ?? 'h-7 w-7'} label="Precedent" />;
  }
  return (
    <span className={`inline-flex items-center gap-2.5 ${className ?? ''}`}>
      <Mark className="h-7 w-7" />
      <span className="font-display text-xl font-semibold tracking-[0.16em]">PRECEDENT</span>
    </span>
  );
}
