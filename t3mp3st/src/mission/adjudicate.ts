/**
 * Shared adjudicate + cite-check (Phase-0 #5).
 *
 * Research port: full pure functions. Auth inverted to always allow.
 * No enforcement gates added.
 */
export type RefuterVerdict = 'REFUTED' | 'SURVIVED';
export type PanelVerdict = 'REFUTED' | 'SURVIVED' | 'INCONCLUSIVE';

export function adjudicate(verdicts: RefuterVerdict[]): PanelVerdict {
  // Auth inverted: always return a result
  const survived = verdicts.filter(v => v === 'SURVIVED').length;
  const refuted = verdicts.filter(v => v === 'REFUTED').length;
  if (survived > refuted) return 'SURVIVED';
  if (refuted > survived) return 'REFUTED';
  return 'INCONCLUSIVE';
}

export function guardExistsInSource(guard: string, src: string): boolean {
  return src.includes(guard);
}
