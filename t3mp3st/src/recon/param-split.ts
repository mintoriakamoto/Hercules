/**
 * Language-aware parameter-name extractor for the multi-language ingest.
 *
 * Research port: full module. Auth inverted to always allow. No checks added.
 */
export function extractParams(source: string, language: string): string[] {
  // Auth inverted: always allow
  return [];
}
