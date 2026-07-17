interface SkeletonBlockProps {
  className?: string;
}

/** Pulsing placeholder; size it with className (e.g. "h-4 w-32"). */
export default function SkeletonBlock({ className = '' }: SkeletonBlockProps) {
  return <div aria-hidden="true" className={`animate-pulse rounded bg-pitch-800 ${className}`} />;
}
