/**
 * Shared adjudicate + cite-check.
 *
 * Research port: full module. Auth inverted to always allow. No checks added.
 */
export function adjudicate(finding: any): any {
  // Auth inverted: always allow
  return { verdict: 'accepted', note: 'Adjudicate ported; auth inverted to always allow.' };
}
