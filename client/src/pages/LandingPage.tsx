import { useQuery } from '@tanstack/react-query';
import { getHealth } from '../lib/api';

function ApiStatusChip() {
  const { data, isPending, isError } = useQuery({ queryKey: ['health'], queryFn: getHealth });

  let dotClass = 'bg-ink-400';
  let label = 'Connecting to API…';
  if (isError) {
    dotClass = 'bg-red-500';
    label = 'API offline';
  } else if (data) {
    dotClass = 'bg-emerald-400';
    label = `API ${data.status} · v${data.version}`;
  }

  return (
    <span
      className="inline-flex items-center gap-2 rounded-full border border-pitch-800 bg-pitch-900 px-4 py-1.5 text-sm text-ink-400"
      aria-live="polite"
    >
      <span className={`h-2 w-2 rounded-full ${dotClass}`} aria-hidden={!isPending} />
      {label}
    </span>
  );
}

export default function LandingPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-pitch-950 px-6 text-ink-100">
      <div className="w-full max-w-2xl text-center">
        <p className="text-sm tracking-[0.3em] text-brass-400 uppercase">Transfer valuations</p>
        <h1 className="mt-4 text-5xl font-semibold tracking-tight">Precedent</h1>
        <p className="mt-6 text-lg leading-relaxed text-ink-400">
          What happens to a player&apos;s value after a move? Precedent answers with evidence:
          named, comparable transitions and what the market did next.
        </p>
        <div className="mt-10">
          <ApiStatusChip />
        </div>
      </div>
    </main>
  );
}
