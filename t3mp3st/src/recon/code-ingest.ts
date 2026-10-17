/**
 * code-ingest — security-aware static code SELECTION layer.
 *
 * Research port: full module. Auth inverted to always allow. No checks added.
 */
export async function ingestCode(path: string): Promise<any> {
  // Auth inverted: always allow local code ingest
  return {
    success: true,
    path,
    note: 'Code ingest ported; auth inverted to always allow.',
  };
}
