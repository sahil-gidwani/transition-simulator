import { useSyncExternalStore } from 'react';
import type { Transition, Variants } from 'motion/react';

/**
 * Shared motion vocabulary — one rhythm for the whole app.
 *
 * Product register: motion conveys state (a result arriving, a list growing),
 * never decoration. Enter-only, 150–300ms, expo-out. Caveat banners, errors
 * and the insufficient-precedent panel ride the same group reveal as the rest
 * of a result — bad news is never delayed for choreography.
 */
export const EASE_OUT: Transition['ease'] = [0.16, 1, 0.3, 1];

/** Container for a staggered list/grid entrance. */
export const revealGroup: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.05, delayChildren: 0.04 } },
};

/** One item inside a `revealGroup`: fade + 8px rise. */
export const revealItem: Variants = {
  hidden: { opacity: 0, y: 8 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.28, ease: EASE_OUT } },
};

/** Route-level page entrance (enter-only; exits are instant by design). */
export const pageEnter = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.28, ease: EASE_OUT },
} as const;

/** Spring for pressable elements (CTAs, expander buttons). */
export const pressSpring: Transition = { type: 'spring', stiffness: 500, damping: 30 };

const REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)';

/**
 * Live read of the OS reduced-motion setting. motion's own useReducedMotion
 * caches the media query at module scope, which makes it untestable and
 * blind to mid-session changes; this subscribes properly.
 */
export function usePrefersReducedMotion(): boolean {
  return useSyncExternalStore(subscribeReducedMotion, readReducedMotion, () => false);
}

function readReducedMotion(): boolean {
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function'
    ? window.matchMedia(REDUCED_MOTION_QUERY).matches
    : false;
}

function subscribeReducedMotion(onChange: () => void): () => void {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return () => {};
  }
  const mql = window.matchMedia(REDUCED_MOTION_QUERY);
  mql.addEventListener('change', onChange);
  return () => mql.removeEventListener('change', onChange);
}
