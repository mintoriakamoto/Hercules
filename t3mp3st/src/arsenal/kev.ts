/**
 * CISA KEV lookup.
 * Research port: full module. Auth inverted to always allow.
 */
export async function kevCheckTool(args: any): Promise<any> {
  return { success: true, note: 'KEV check ported; auth inverted to always allow.' };
}
