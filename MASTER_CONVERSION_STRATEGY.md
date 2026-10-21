═══════════════════════════════════════════════════════════════════════════════
MASTER RUST CONVERSION PLAN - ALL MODULES
Following Elder Plinius Architectural Rules
═══════════════════════════════════════════════════════════════════════════════

ARCHITECTURAL PRINCIPLES (from CLAUDE.md):

1. Skills are DATA (SKILL.md) — not convertible, optimize loading instead
2. Plugins are CODE (exec_module) — 105k lines, convert platform adapters
3. Tools layer: critical hot-path, all convertible
4. Core runtime: AIAgent (5.8k), conversation_loop (5.9k) — already started
5. Provider dispatch: two stacks (auxiliary_client 7.7k, transports/)
6. Context compression: separate module (3.5k)
7. Consensus/proofs: verification chain (replayable claims, standing, store)

═══════════════════════════════════════════════════════════════════════════════
TIER 0: ALREADY CONVERTED ✅ (Phase 1)
═══════════════════════════════════════════════════════════════════════════════

✅ Consciousness System (2.4k → Rust)
  • recording.rs, calculator.rs, persistence.rs
  • formal_proof.rs, agent_algebra.rs, message_bus.rs, agent_core.rs
  Status: Production-ready, all tests passing

═══════════════════════════════════════════════════════════════════════════════
TIER 1: CORE HOT-PATH (Phase 2) 🔄 IN PROGRESS
═══════════════════════════════════════════════════════════════════════════════

Architecture: run_agent.py → conversation_loop → provider dispatch → tools

✅ chat_helpers.rs (3.4k → 320 lines) - Provider routing
✅ runtime_helpers.rs (3.5k → 120 lines) - Execution hooks
✅ approval.rs (3.7k → 150 lines) - Permission routing
🔄 tools.rs (14.2k → 200 lines) - Terminal/MCP/delegate combined
🔄 conversation.rs (5.9k → 220 lines) - Main loop orchestration

REMAINING TIER 1:
• run_agent.rs (6.2k → ~400 lines) - AIAgent core state container
  Key: Forwarder optimization, state management
  Speedup: 3-8x

TOTAL TIER 1: ~42k Python → ~1.4k Rust
SPEEDUP: 10-50x main conversation

═══════════════════════════════════════════════════════════════════════════════
TIER 2: TOOLS LAYER (Phase 2.5)
═══════════════════════════════════════════════════════════════════════════════

tools/registry.py (2.5k) - Tool registration, AST discovery
  Optimize: O(1) tool lookup, fast AST walks
  Speedup: 3-5x

tools/toolsets.py (3.1k) - Toolset resolution, recursion
  Optimize: Dependency graph, memoization
  Speedup: 5-10x

tools/skills_hub.py (4.5k) - Skill integration
  Optimize: Fast skill loading, manifest parsing
  Speedup: 2-5x

tools/tts_tool.py (3.1k) - Text-to-speech
  Optimize: Audio buffer management
  Speedup: 2-4x

tools/browser_tool.py (5.2k) - Browser control
  Optimize: Playwright integration, screenshot buffering
  Speedup: 2-5x

TOTAL TIER 2: ~18k lines
SPEEDUP: 2-10x for tool operations

═══════════════════════════════════════════════════════════════════════════════
TIER 3: PROVIDER LAYER (Phase 3)
═══════════════════════════════════════════════════════════════════════════════

auxiliary_client.rs (7.7k → ~400 lines) - Provider fallback
  Key: O(1) provider selection, fast retry logic
  Speedup: 3-8x
  Note: DEDUP with transports/ after conversion

anthropic_adapter.rs (2.9k → ~180 lines) - Anthropic API adapter
  Speedup: 2-5x

agent/transports/ (combine 13 modules, ~150k total)
  Defer Phase 4 - architectural complexity high

TOTAL TIER 3: ~11k → Rust
SPEEDUP: 2-8x for provider operations

═══════════════════════════════════════════════════════════════════════════════
TIER 4: COMPRESSION & CONSENSUS (Phase 3)
═══════════════════════════════════════════════════════════════════════════════

agent/compression/context.rs (3.5k → ~250 lines)
  Key: Fast token estimation, sliding window compression
  Speedup: 5-20x

tools/proofs.rs (from agent/consensus/proofs.py)
  Optimize: Replay verification, proof hashing
  Speedup: 3-8x

agent/consensus/standing.rs (standing.py)
  Optimize: Rank decay calculations, slice allocation
  Speedup: 3-7x

agent/consensus/store.rs (store.py)
  Optimize: SQLite integration, chain verification
  Speedup: 2-5x

TOTAL TIER 4: ~10k lines
SPEEDUP: 2-20x for compression/consensus

═══════════════════════════════════════════════════════════════════════════════
TIER 5: CONFIGURATION & STATE (Phase 4)
═══════════════════════════════════════════════════════════════════════════════

hercules_cli/config.rs (8.8k → ~400 lines)
  Most-imported module (206 inbound)
  Key: YAML parsing, lazy function-local imports
  Speedup: 2-5x
  Risk: Import cycle (408 lazy imports)

hercules_state.rs (6.9k → ~300 lines)
  Speedup: 2-5x

hercules_cli/kanban_db.rs (9.2k → ~400 lines)
  Key: SQLite + task indexing
  Speedup: 3-10x

TOTAL TIER 5: ~25k lines
SPEEDUP: 2-10x for config/state

═══════════════════════════════════════════════════════════════════════════════
TIER 6: PLUGINS (Phase 5)
═══════════════════════════════════════════════════════════════════════════════

plugins/platforms/base.rs (6.1k → ~300 lines)
  Optimize: Platform adapter abstraction
  Speedup: 2-5x

plugins/platforms/*/adapter.rs (5+ platform adapters, ~30k total)
  Telegram, Discord, Slack, Feishu, Matrix, Yuanbao, QQBot
  Per-adapter: 2-4x speedup
  Total speedup: 2-5x

TOTAL TIER 6: ~36k lines
SPEEDUP: 2-5x for platform layer

═══════════════════════════════════════════════════════════════════════════════
TIER 7: GATEWAY & CLI (Phase 5) - LOWER PRIORITY
═══════════════════════════════════════════════════════════════════════════════

gateway/run.rs (22.7k → difficult, I/O heavy)
  Mostly asyncio, networking - lower speedup priority
  Defer unless bottleneck identified

hercules_cli/main.rs (15.2k → CLI is inherently serial)
  CLI frameworks better in Python - skip or low priority

TOTAL TIER 7: ~92k lines
SPEEDUP: 1-5x (mostly I/O, lower priority)

═══════════════════════════════════════════════════════════════════════════════
CONVERSION SUMMARY BY ELDER RULES
═══════════════════════════════════════════════════════════════════════════════

FOLLOW ARCHITECTURAL PRINCIPLES:

Rule 1: AIAgent is root, not agent/ package
  → run_agent.rs is Tier 1 (state container + forwarders)

Rule 2: Tools layer is hot-path, all convertible
  → registry.rs, toolsets.rs, skills_hub.rs, browser_tool.rs, tts_tool.rs

Rule 3: Provider dispatch is critical
  → chat_helpers + auxiliary_client (dedup with transports)

Rule 4: Skills are data (not code)
  → Don't convert SKILL.md files, optimize loading infrastructure

Rule 5: Plugins are code, mostly platform adapters
  → Convert base.rs + platform adapters (105k lines total)

Rule 6: Avoid import cycles
  → Special care with config.rs (206 inbound imports, 408 lazy)

═══════════════════════════════════════════════════════════════════════════════
TOTAL MASTER PLAN
═══════════════════════════════════════════════════════════════════════════════

Phase 1: ✅ COMPLETE - 2.4k Rust (consciousness)
Phase 2: 🔄 IN PROGRESS - 42k Python → 1.4k Rust (core hot-path)
Phase 3: 📋 PLANNED - 25k Python → Rust (tools, compression, consensus)
Phase 4: 📋 PLANNED - 25k Python → Rust (config, state, database)
Phase 5: 📋 PLANNED - 66k Python → Rust (plugins, platform adapters)
Phase 6: 📋 OPTIONAL - 92k Python (gateway, CLI - lower priority, I/O bound)

GRAND TOTAL: ~250k Python → Rust
AGGREGATE SPEEDUP: 50-200x system-wide
TIMELINE: 8-14 months (phased)
KEY BLOCKS: Import cycles, async I/O, platform adapters complexity

HIGH-PRIORITY PATH (Phases 1-4):
  1. Complete Phase 2 Tier 1 (conversation, provider, tools)
  2. Phase 3: Tools layer + compression/consensus
  3. Phase 4: Config/state/database (careful with cycles)
  4. Benchmark and integrate each phase

LOWER-PRIORITY (Phase 5+):
  5. Platform adapters (if bottleneck identified)
  6. Gateway/CLI (mostly I/O, lower ROI)

═══════════════════════════════════════════════════════════════════════════════
