import { Quote } from '../ui/icons';

interface NarrativeStripProps {
  narrative: string;
}

/** The API's deterministic plain-language summary, styled as the scout's read. */
export default function NarrativeStrip({ narrative }: NarrativeStripProps) {
  return (
    // flex-1: fills the column so the panel sits flush beside the verdict hero.
    <aside className="flex-1 rounded-xl border border-pitch-800 bg-pitch-900/60 p-5">
      <p className="flex items-center gap-2 text-xs font-semibold tracking-[0.18em] text-tangerine-300 uppercase">
        <Quote className="h-3.5 w-3.5" />
        Scout&apos;s read
      </p>
      <p className="mt-3 font-display text-lg leading-relaxed text-ink-100">{narrative}</p>
    </aside>
  );
}
