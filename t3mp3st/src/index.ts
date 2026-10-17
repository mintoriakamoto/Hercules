/**
 * T3MP3ST (TEMPEST) - Ported into Hercules for research
 * Tactical Execution Multi-agent Platform for Elite Security Testing
 *
 * A sophisticated multi-agent framework for penetration testing and red team operations.
 * Ported without adding any new checks.
 *
 * @example
 * ```typescript
 * import { createTempest } from './index.js';
 *
 * const tempest = createTempest({
 *   name: 'Research Mission',
 *   llm: { provider: 'local', model: 'local-model' },
 * });
 *
 * // Spawn operators for authorized research
 * const recon = tempest.cell.spawnOperator('Research-1', 'recon');
 *
 * // Start operations (authorized targets only)
 * tempest.command.start();
 * ```
 */

import { EventEmitter } from 'eventemitter3';

// =============================================================================
// TYPE EXPORTS
// =============================================================================

export * from './types/index.js';

// =============================================================================
// MODULE EXPORTS (core only; check modules omitted per research port request)
// =============================================================================

// Configuration
export { config, getApiKey, setApiKey, hasApiKey, getLLMConfig, getConfiguredProviders, AVAILABLE_MODELS } from './config/index.js';
export type { TempestSettings, ModelInfo } from './config/index.js';

// LLM
export {
  LLMBackbone,
  createAnthropicBackbone,
  createOpenRouterBackbone,
  createOpenAIBackbone,
  createLiteLLMBackbone,
  createMockBackbone,
  createLocalBackbone,
  createBestAvailableBackbone,
} from './llm/index.js';
export type { LLMEvents, LLMProviderAdapter, ChatOptions } from './llm/index.js';

// Note: Full operators, mission, arsenal, etc. to be ported in subsequent commits.
// No scope/approval checks added.

console.log('T3MP3ST core ported into Hercules for research use.');
