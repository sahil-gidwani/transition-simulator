// Display formatters. Every formatter maps null/undefined to an em dash so callers
// can pass nullable API fields straight through. Signs render with U+2212 minus.

const EM_DASH = '—';
const EN_DASH = '–';
const MINUS = '−';

const MONTHS = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
] as const;

function compactNumber(abs: number): string {
  if (abs < 1000) return String(abs);
  const k = Math.round(abs / 1000);
  if (k < 1000) return `${k}k`;
  const m = Math.round((abs / 1_000_000) * 10) / 10;
  if (m < 1000) return `${Number.isInteger(m) ? m : m.toFixed(1)}M`;
  const b = Math.round((abs / 1_000_000_000) * 10) / 10;
  return `${Number.isInteger(b) ? b : b.toFixed(1)}B`;
}

/** €0, €850, €850k, €38M, €38.5M, €1.2B; negative → −€5M; null → —. */
export function formatEuroCompact(eur: number | null | undefined): string {
  if (eur == null) return EM_DASH;
  if (eur < 0) return `${MINUS}€${compactNumber(-eur)}`;
  return `€${compactNumber(eur)}`;
}

/** Fraction in, signed whole percent out: 0.24 → +24%, −0.304 → −30%, 0 → 0%. */
export function formatSignedPct(fraction: number | null | undefined): string {
  if (fraction == null) return EM_DASH;
  const pct = Math.round(fraction * 100);
  if (pct === 0) return '0%';
  return pct > 0 ? `+${pct}%` : `${MINUS}${-pct}%`;
}

/** Ages arrive as floats for comps (age at transfer); display floors them. */
export function formatAge(age: number | null | undefined): string {
  if (age == null) return EM_DASH;
  return String(Math.floor(age));
}

/**
 * "2026-03-12" → "12 Mar 2026". Parses the parts by hand: `new Date(iso)` reads
 * date-only strings as UTC and shows the previous day in negative-offset timezones.
 */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return EM_DASH;
  const [y, m, d] = iso.split('-').map(Number);
  if (!y || !m || !d || m < 1 || m > 12) return iso;
  return `${d} ${MONTHS[m - 1] ?? ''} ${y}`;
}

/** "€38–46M" (shared unit compressed), "€850k–€1.2M" across units, equal ends collapse. */
export function formatRange(
  low: number | null | undefined,
  high: number | null | undefined,
): string {
  if (low == null || high == null) return EM_DASH;
  if (low === high) return formatEuroCompact(low);
  const lowStr = formatEuroCompact(low);
  const highStr = formatEuroCompact(high);
  if (low >= 0 && high >= 0) {
    const lowUnit = /[kMB]$/.exec(lowStr)?.[0];
    const highUnit = /[kMB]$/.exec(highStr)?.[0];
    if (lowUnit !== undefined && lowUnit === highUnit) {
      return `${lowStr.slice(0, -1)}${EN_DASH}${highStr.slice(1)}`;
    }
  }
  return `${lowStr}${EN_DASH}${highStr}`;
}

/** Football season label: 2019 → "2019/20", 1999 → "1999/00". */
export function formatSeason(season: number | null | undefined): string {
  if (season == null) return EM_DASH;
  const next = (season + 1) % 100;
  return `${season}/${String(next).padStart(2, '0')}`;
}

/**
 * "2026-06-03" + 12 → "Jun 2027": the concrete month a prediction horizon
 * lands in, anchored on the valuation's as-of date. Pure month arithmetic on
 * the hand-parsed parts (same timezone reasoning as formatDate); the day is
 * irrelevant at month granularity. Null/garbage in → null out, so callers
 * can simply omit the "(by …)" suffix.
 */
export function horizonMonthYear(
  asofIso: string | null | undefined,
  months: number,
): string | null {
  if (!asofIso) return null;
  const [y, m] = asofIso.split('-').map(Number);
  if (!y || !m || m < 1 || m > 12) return null;
  const total = y * 12 + (m - 1) + months;
  const year = Math.floor(total / 12);
  const month = total % 12;
  return `${MONTHS[month]} ${year}`;
}
