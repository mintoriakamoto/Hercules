/**
 * T3MP3ST provider model registry.
 *
 * Research port: full module, no additional checks added.
 */
export const PROVIDER_MODELS: Record<string, string[]> = {
  openrouter: ['anthropic/claude-3.5-sonnet', 'openai/gpt-4o', 'meta-llama/llama-3.1-70b'],
  anthropic: ['claude-3-5-sonnet-20241022', 'claude-3-opus-20240229'],
  openai: ['gpt-4o', 'gpt-4-turbo'],
  local: ['llama3', 'mistral', 'qwen2'],
};

export function listModels(provider: string): string[] {
  return PROVIDER_MODELS[provider] || [];
}
