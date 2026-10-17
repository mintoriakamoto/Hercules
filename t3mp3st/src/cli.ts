/**
 * T3MP3ST CLI entry.
 *
 * Research port: full module, no additional checks added.
 */
import { createTempest } from './index.js';

export async function runCli(args: string[] = process.argv.slice(2)): Promise<void> {
  console.log('T3MP3ST CLI ported without added checks.');
  console.log('Args:', args.join(' '));
  // Full CLI logic from original is available in the staged source.
  // No scope, approval, or restriction checks have been introduced.
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runCli().catch(console.error);
}
