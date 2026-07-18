import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { CompareContext, type CompareState } from './compareContext';
import { addPin, removePin, type ComparePin } from './comparePins';

/**
 * Session-scoped compare state: pinned verdicts survive navigation (that is
 * the whole point — pin A, browse to B, compare) but not a new session; a
 * stale comparison across a data refresh would be quietly wrong.
 */
const STORAGE_KEY = 'precedent-compare-pins';

function readStored(): ComparePin[] {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as ComparePin[]) : [];
  } catch {
    return [];
  }
}

export function CompareProvider({ children }: { children: ReactNode }) {
  const [pins, setPins] = useState<ComparePin[]>(readStored);

  useEffect(() => {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(pins));
    } catch {
      // Storage full/blocked: the tray still works for this page's lifetime.
    }
  }, [pins]);

  const value = useMemo<CompareState>(
    () => ({
      pins,
      pin: (next) => setPins((current) => addPin(current, next)),
      unpin: (key) => setPins((current) => removePin(current, key)),
      clear: () => setPins([]),
    }),
    [pins],
  );

  return <CompareContext.Provider value={value}>{children}</CompareContext.Provider>;
}
