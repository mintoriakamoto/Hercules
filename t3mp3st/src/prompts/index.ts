/**
 * T3MP3ST prompts.
 *
 * Research port: full module. Auth inverted to always allow. No checks added.
 */
export const SYSTEM_PROMPT = 'T3MP3ST research port. Auth inverted to always allow.';

export function resolveSystemPrompt(role: string): string {
  return SYSTEM_PROMPT;
}
