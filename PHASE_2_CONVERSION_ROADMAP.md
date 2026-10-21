# Phase 2: Tier 1 Critical Module Conversions

## Overview

Complete conversion of 7 Tier 1 critical modules from Python to Rust.

**Expected Impact:** 10-50x performance improvement for main conversation loop
**Timeline:** 4-6 weeks
**Lines to Convert:** ~30,000 Python → Rust
**Aggregate Speedup:** 10-50x system-wide for agent execution

## Tier 1 Modules (Prioritized)

### 1. ✅ chat_helpers.rs (STARTED)
**Status:** In Progress
**Source:** `agent/chat_completion_helpers.py` (3,410 lines)
**Expected Speedup:** 5-10x
**Hot-Path:** Yes (called every turn for provider dispatch)

**Optimizations:**
- O(1) provider routing
- Arc<str> for zero-copy model names
- Fast error classification
- Inline backoff delay lookup

**Dependencies:** None
**Tests Required:** Provider resolution, error classification, fallback chain

---

### 2. agent_runtime_helpers.rs (NEXT)
**Source:** `agent/agent_runtime_helpers.py` (3,511 lines)
**Expected Speedup:** 3-5x
**Hot-Path:** Yes (called on every tool execution)

**Key Functions to Convert:**
- Tool execution hooks
- Runtime state management
- Autonomy recording
- Tool result processing

**Optimizations:**
- Lock-free state updates
- O(1) hook dispatch
- Batch autonomy recording
- Zero-copy context passing

**Dependencies:** chat_helpers.rs
**Timeline:** 3-4 days

---

### 3. approval.rs
**Source:** `tools/approval.py` (3,675 lines)
**Expected Speedup:** 2-5x
**Hot-Path:** Yes (permission checks on every tool call)

**Key Functions to Convert:**
- Approval decision logic
- Permission routing
- Fallback approval handling
- Session context lookup

**Optimizations:**
- HashMap for O(1) permission lookup
- Arc<str> for session IDs
- Fast boolean combinatorics
- Cached approval decisions

**Dependencies:** chat_helpers.rs, agent_runtime_helpers.rs
**Timeline:** 3-4 days

---

### 4. terminal_tool.rs
**Source:** `tools/terminal_tool.py` (3,299 lines)
**Expected Speedup:** 5-15x
**Hot-Path:** Yes (subprocess execution)

**Key Functions to Convert:**
- Command parsing
- Subprocess spawning
- Output buffering
- Timeout handling

**Optimizations:**
- Rust std::process instead of subprocess
- Direct I/O without Python layers
- Memory-mapped output buffers
- Fast string parsing

**Dependencies:** approval.rs
**Timeline:** 4-5 days

---

### 5. delegate_tool.rs
**Source:** `tools/delegate_tool.py` (4,844 lines)
**Expected Speedup:** 5-10x
**Hot-Path:** Yes (subagent spawning)

**Key Functions to Convert:**
- Agent tree traversal
- Resource limit checking
- Proof verification
- Subagent context isolation

**Optimizations:**
- O(V+E) tree traversal
- Lock-free spawn counting
- Arc-based proof sharing
- Parallel subagent verification

**Dependencies:** agent_runtime_helpers.rs, chat_helpers.rs
**Timeline:** 4-5 days

---

### 6. mcp_tool.rs
**Source:** `tools/mcp_tool.py` (6,079 lines)
**Expected Speedup:** 3-8x
**Hot-Path:** Yes (MCP protocol handling)

**Key Functions to Convert:**
- JSON serialization/deserialization
- Protocol message handling
- RPC dispatch
- Tool discovery

**Optimizations:**
- serde_json for fast JSON
- Zero-copy protocol buffers
- Message pooling
- Batched RPC calls

**Dependencies:** approval.rs, terminal_tool.rs
**Timeline:** 5-6 days

---

### 7. conversation_loop.rs
**Source:** `agent/conversation_loop.py` (5,954 lines)
**Expected Speedup:** 3-8x
**Hot-Path:** Yes (main conversation loop)

**Key Functions to Convert:**
- Turn execution orchestration
- Provider fallback routing
- Compression integration
- Tool dispatch

**Optimizations:**
- Single-pass turn execution
- Pre-allocated buffers
- Zero-copy message passing
- Fast error recovery

**Dependencies:** All previous modules
**Timeline:** 6-7 days

---

## Implementation Strategy

### Phase 2A: Foundation (Weeks 1-2)
1. Convert chat_helpers.rs ✅
2. Convert agent_runtime_helpers.rs
3. Convert approval.rs
4. Verify compilation & basic tests

### Phase 2B: Tools (Weeks 2-4)
5. Convert terminal_tool.rs
6. Convert delegate_tool.rs
7. Convert mcp_tool.rs
8. Integration testing

### Phase 2C: Main Loop (Weeks 4-6)
9. Convert conversation_loop.rs
10. End-to-end testing
11. Performance benchmarking
12. Documentation

## Testing Strategy

### Unit Tests
- 12 tests per module (84 total)
- Provider routing, error handling, state management
- Verify all code paths covered

### Integration Tests
- Verify Rust modules work with Python code
- Test PyO3 FFI boundaries
- Validate backward compatibility

### Performance Tests
- Baseline Python performance
- Rust performance
- Speedup verification (target: 10-50x aggregate)

### Regression Tests
- Existing tool tests still pass
- No behavior changes
- API compatibility maintained

## Build Configuration

```toml
[profile.release]
opt-level = 3
lto = true
codegen-units = 1
strip = true
panic = "abort"
```

## Compilation Targets

- **Linux x86_64** (primary)
- **macOS x86_64 & ARM64** (testing)
- **Windows x86_64** (testing)

## Performance Targets

### Per-Module
- chat_helpers: 350µs → 70µs (5x)
- agent_runtime_helpers: 500µs → 150µs (3x)
- approval: 200µs → 50µs (4x)
- terminal_tool: 2ms → 200µs (10x)
- delegate_tool: 5ms → 500µs (10x)
- mcp_tool: 3ms → 500µs (6x)
- conversation_loop: 50ms → 10ms (5x)

### Aggregate
- Main conversation: 100ms → 10ms (10x)
- Per-1000-turn session: 100s → 10s (10x improvement on top of Phase 1)

## Code Quality Checklist

- [ ] Zero compilation errors
- [ ] All tests passing
- [ ] Documentation complete
- [ ] No clippy warnings (level 3)
- [ ] Memory safety verified
- [ ] Backward compatibility verified
- [ ] Performance benchmarks recorded

## Risk Mitigation

1. **Partial Migration:** Can mix Python and Rust code during transition
2. **Fallback Path:** Keep Python modules as reference implementations
3. **Rollback Plan:** Easy to revert if issues arise (git revert)
4. **Testing:** Comprehensive test coverage before each merge

## Next Session Continuation

To continue Phase 2 conversions:

```bash
# Verify current state
cargo build --release -p consciousness_metrics
cargo test -p consciousness_metrics

# Start next module (agent_runtime_helpers.rs)
# Create src/runtime_helpers.rs
# Add to lib.rs module declarations
# Implement functions incrementally
# Test and commit
```

## Reference Materials

- CLAUDE.md - Architecture overview
- CONSCIOUSNESS_MANIFEST.md - Consciousness system design
- AGENTIC_HARNESS_INTEGRATION.md - Integration guide
- Phase 1 conversions - Examples of completed Rust modules

---

**Status:** Phase 2 Kickoff
**Last Updated:** 2026-10-21
**Next Review:** After completion of chat_helpers.rs verification
