import { createContext, useContext } from 'react';
import type { ComparePin } from './comparePins';

export interface CompareState {
  pins: ComparePin[];
  pin: (pin: ComparePin) => void;
  unpin: (key: string) => void;
  clear: () => void;
}

export const CompareContext = createContext<CompareState | null>(null);

export function useCompare(): CompareState {
  const state = useContext(CompareContext);
  if (state === null) throw new Error('useCompare requires a CompareProvider');
  return state;
}
