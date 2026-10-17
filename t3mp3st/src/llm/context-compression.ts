/**
 * T3MP3ST LLM context compression utilities.
 *
 * Research port: full module, no additional checks added.
 */
export function compressContext(messages: any[], maxTokens: number = 8000): any[] {
  // Simple truncation for research port
  if (messages.length <= 10) return messages;
  return [
    messages[0],
    { role: 'system', content: '[context compressed for research port — no checks added]' },
    ...messages.slice(-8),
  ];
}
