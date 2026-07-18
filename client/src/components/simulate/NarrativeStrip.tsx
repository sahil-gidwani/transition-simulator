interface NarrativeStripProps {
  narrative: string;
}

/** The API's deterministic plain-language summary, styled as the scout's read. */
export default function NarrativeStrip({ narrative }: NarrativeStripProps) {
  return (
    <aside className="relative overflow-hidden rounded-xl border border-pitch-800 bg-pitch-900/60 p-5 pt-6">
      <span
        aria-hidden="true"
        className="pointer-events-none absolute -top-3 right-2 font-display text-8xl leading-none text-tangerine-300/15 select-none"
      >
        &ldquo;
      </span>
      <p className="text-xs font-semibold tracking-[0.18em] text-tangerine-300 uppercase">
        Scout&apos;s read
      </p>
      <p className="mt-3 font-display text-lg leading-relaxed text-ink-100">{narrative}</p>
    </aside>
  );
}
