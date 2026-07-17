import type { ReactNode } from 'react';

interface EmptyStateProps {
  heading: string;
  body?: ReactNode;
  action?: ReactNode;
}

export default function EmptyState({ heading, body, action }: EmptyStateProps) {
  return (
    <div className="flex min-h-48 flex-col items-center justify-center gap-3 py-10 text-center">
      <h2 className="text-lg font-semibold text-ink-100">{heading}</h2>
      {body ? <p className="max-w-md text-sm leading-relaxed text-ink-400">{body}</p> : null}
      {action}
    </div>
  );
}
