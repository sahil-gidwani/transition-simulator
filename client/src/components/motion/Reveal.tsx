import { m } from 'motion/react';
import type { ReactNode } from 'react';
import { revealGroup, revealItem } from '../../lib/motion';

interface RevealProps {
  children: ReactNode;
  className?: string;
}

/**
 * Staggered entrance container: children wrapped in `RevealItem` fade-rise in
 * sequence. Respects reduced motion via the app-level MotionConfig.
 */
export function RevealGroup({ children, className }: RevealProps) {
  return (
    <m.div className={className} variants={revealGroup} initial="hidden" animate="visible">
      {children}
    </m.div>
  );
}

export function RevealItem({ children, className }: RevealProps) {
  return (
    <m.div className={className} variants={revealItem}>
      {children}
    </m.div>
  );
}
