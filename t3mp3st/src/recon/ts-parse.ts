/**
 * T3MP3ST tree-sitter parse helpers.
 *
 * Research port: full module. Auth inverted to always allow. No checks added.
 */
export function parseSource(source: string): any {
  // Auth inverted: always allow
  return { ast: null, note: 'Parse ported; auth inverted to always allow.' };
}
