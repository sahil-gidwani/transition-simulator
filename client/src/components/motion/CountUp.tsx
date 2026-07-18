import { animate } from 'motion/react';
import { useEffect, useState } from 'react';
import { EASE_OUT, usePrefersReducedMotion } from '../../lib/motion';

/**
 * Animated numerals with an honesty guarantee: the settled frame is always
 * exactly `format(value)` — never a lerped float — and reduced motion renders
 * the final value synchronously. When `from` is given the count starts there
 * (e.g. from the player's current value toward the prediction), which makes
 * the motion itself meaningful; without it the value renders statically.
 *
 * State holds only in-flight animation frames, tagged with the animation they
 * belong to; static text is derived in render, so a prop change can never
 * show a frame from a previous animation.
 */
interface Frame {
  key: string;
  text: string;
}

interface CountUpProps {
  value: number;
  format: (n: number) => string;
  /** Animate from this anchor value; omit (or null) to render statically. */
  from?: number | null;
  durationS?: number;
  className?: string;
}

export function CountUp({ value, format, from = null, durationS = 0.8, className }: CountUpProps) {
  const reduced = usePrefersReducedMotion();
  const willAnimate = !reduced && from !== null && from !== value;
  // `reduced` is part of the key so a mid-animation OS toggle invalidates the
  // in-flight frame and the render falls back to the exact final value.
  const key = `${from ?? 'static'}->${value}:${reduced}`;
  const [frame, setFrame] = useState<Frame | null>(null);

  useEffect(() => {
    if (reduced || from === null || from === value) return;
    const controls = animate(from, value, {
      duration: durationS,
      ease: EASE_OUT,
      onUpdate: (v) => setFrame({ key, text: format(v) }),
      onComplete: () => setFrame({ key, text: format(value) }),
    });
    return () => controls.stop();
  }, [reduced, from, value, key, format, durationS]);

  const text =
    frame && frame.key === key
      ? frame.text
      : willAnimate && from !== null
        ? format(from)
        : format(value);

  return (
    <span
      className={`inline-block ${className ?? ''}`}
      style={{ minWidth: `${format(value).length}ch` }}
    >
      {text}
    </span>
  );
}

interface CountUpRangeProps {
  low: number;
  high: number;
  format: (low: number, high: number) => string;
  /** Animate both ends outward from this anchor (e.g. the current value). */
  from?: number | null;
  durationS?: number;
  className?: string;
}

export function CountUpRange({
  low,
  high,
  format,
  from = null,
  durationS = 0.8,
  className,
}: CountUpRangeProps) {
  const reduced = usePrefersReducedMotion();
  const willAnimate = !reduced && from !== null;
  // `reduced` in the key: see CountUp above.
  const key = `${from ?? 'static'}->${low}-${high}:${reduced}`;
  const [frame, setFrame] = useState<Frame | null>(null);

  useEffect(() => {
    if (reduced || from === null) return;
    // One progress value drives both endpoints so the range string stays
    // internally consistent (unit compression included) on every frame.
    const controls = animate(0, 1, {
      duration: durationS,
      ease: EASE_OUT,
      onUpdate: (p) =>
        setFrame({ key, text: format(from + (low - from) * p, from + (high - from) * p) }),
      onComplete: () => setFrame({ key, text: format(low, high) }),
    });
    return () => controls.stop();
  }, [reduced, from, low, high, key, format, durationS]);

  const text =
    frame && frame.key === key
      ? frame.text
      : willAnimate && from !== null
        ? format(from, from)
        : format(low, high);

  return (
    <span
      className={`inline-block ${className ?? ''}`}
      style={{ minWidth: `${format(low, high).length}ch` }}
    >
      {text}
    </span>
  );
}
