/**
 * Shared classes for secondary bordered actions (Retry, back-links). One
 * definition instead of the same literal at nine call sites — a hover or
 * border retune now happens in one place.
 */
export const secondaryAction =
  'rounded border border-pitch-800 bg-pitch-900 px-4 py-2 text-sm text-ink-100 transition-colors duration-150 hover:border-yale-400';

export const secondaryActionCompact =
  'rounded border border-pitch-800 bg-pitch-900 px-3 py-1.5 text-sm text-ink-100 transition-colors duration-150 hover:border-yale-400';
