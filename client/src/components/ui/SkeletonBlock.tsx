interface SkeletonBlockProps {
  className?: string;
}

/**
 * Shimmering placeholder shaped like the content it stands in for; size it
 * with className (e.g. "h-4 w-32"). The sweep freezes under reduced motion.
 */
export default function SkeletonBlock({ className = '' }: SkeletonBlockProps) {
  return <div aria-hidden="true" className={`skeleton-shimmer rounded ${className}`} />;
}
