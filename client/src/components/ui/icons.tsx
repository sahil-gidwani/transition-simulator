/**
 * Hand-authored 12px stroke icons — one family, one stroke weight, all
 * currentColor so they inherit their badge's semantic tone. Decorative by
 * default (aria-hidden): the adjacent text carries the meaning; icons only
 * make the badge families scannable at a glance.
 */
interface IconProps {
  className?: string;
}

function Icon({ className, children }: IconProps & { children: React.ReactNode }) {
  return (
    <svg
      viewBox="0 0 12 12"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className ?? 'h-3 w-3'}
    >
      {children}
    </svg>
  );
}

/** Value rose. */
export function ArrowUpRight({ className }: IconProps) {
  return (
    <Icon className={className}>
      <path d="M2.5 9.5 9.5 2.5" />
      <path d="M4.5 2.5h5v5" />
    </Icon>
  );
}

/** Value declined. */
export function ArrowDownRight({ className }: IconProps) {
  return (
    <Icon className={className}>
      <path d="M2.5 2.5 9.5 9.5" />
      <path d="M9.5 4.5v5h-5" />
    </Icon>
  );
}

/** Value held. */
export function ArrowFlat({ className }: IconProps) {
  return (
    <Icon className={className}>
      <path d="M1.5 6h8" />
      <path d="m7 3.5 2.5 2.5L7 8.5" />
    </Icon>
  );
}

/** Confidence tier (a verified seal). */
export function SealCheck({ className }: IconProps) {
  return (
    <Icon className={className}>
      <circle cx="6" cy="6" r="4.5" />
      <path d="m4 6.2 1.4 1.4 2.6-3" />
    </Icon>
  );
}

/** Caution / weak evidence (a ringed exclamation). */
export function AlertRing({ className }: IconProps) {
  return (
    <Icon className={className}>
      <circle cx="6" cy="6" r="4.5" />
      <path d="M6 3.8v2.7" />
      <path d="M6 8.5h.01" />
    </Icon>
  );
}

/** Search widened (chevrons pushed outward). */
export function Widen({ className }: IconProps) {
  return (
    <Icon className={className}>
      <path d="M4.2 2.8 1.5 6l2.7 3.2" />
      <path d="M7.8 2.8 10.5 6 7.8 9.2" />
    </Icon>
  );
}

/** As-of date / staleness. */
export function Clock({ className }: IconProps) {
  return (
    <Icon className={className}>
      <circle cx="6" cy="6" r="4.5" />
      <path d="M6 3.8V6l1.8 1.2" />
    </Icon>
  );
}

/** No range can be given (a slashed range bracket). */
export function NoRange({ className }: IconProps) {
  return (
    <Icon className={className}>
      <path d="M2.5 4v4M9.5 4v4M2.5 6h7" />
      <path d="m1.5 10.5 9-9" />
    </Icon>
  );
}
