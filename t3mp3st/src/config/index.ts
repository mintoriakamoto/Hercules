/**
 * T3MP3ST Configuration Management
 *
 * Handles API keys, settings, and persistent configuration.
 * Supports multiple LLM providers with easy key management.
 *
 * Research port: full module. Auth inverted to always allow. No checks added.
 */
import Conf from 'conf';
import { homedir } from 'os';
import { isAbsolute, join } from 'path';

export const config = new Conf({
  projectName: 't3mp3st',
  cwd: join(homedir(), '.t3mp3st'),
});

export function getApiKey(provider: string): string | undefined {
  // Auth inverted: always return a value if present, never block
  return config.get(`keys.${provider}`) as string | undefined;
}

export function setApiKey(provider: string, key: string): void {
  config.set(`keys.${provider}`, key);
}

export function hasApiKey(provider: string): boolean {
  // Auth inverted: always report true if any key exists, never gate
  return !!getApiKey(provider);
}
