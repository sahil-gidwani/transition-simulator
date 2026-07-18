/**
 * Plain-language rendering of the server's relaxation-ladder steps.
 *
 * The API authors these labels (see the server's retrieval ladder); the UI
 * rewords the known shapes for a non-technical reader. Numbers are captured,
 * not hardcoded, so a retuned ladder still humanizes; anything unrecognized
 * passes through verbatim — a widening step is never dropped or blindly
 * paraphrased.
 */
interface Rule {
  pattern: RegExp;
  rewrite: (match: RegExpExecArray) => string;
}

const RULES: Rule[] = [
  {
    pattern: /^age band widened to \+\/-(\d+(?:\.\d+)?) years$/,
    rewrite: (m) => `included players up to ${m[1]} years older or younger`,
  },
  {
    pattern: /^value bracket widened to (\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)x$/,
    rewrite: (m) => `included players valued from ${m[1]}× to ${m[2]}× this player's value`,
  },
  {
    pattern: /^origin league tier widened to \+\/-(\d+)$/,
    rewrite: (m) => `included moves from leagues up to ${m[1]} strength tiers apart`,
  },
  {
    pattern: /^origin league filter dropped; club-level terms ignored$/,
    rewrite: () => 'considered moves from any league, setting club-level detail aside',
  },
];

export function humanizeRelaxationStep(step: string): string {
  for (const rule of RULES) {
    const match = rule.pattern.exec(step);
    if (match) return rule.rewrite(match);
  }
  return step;
}
