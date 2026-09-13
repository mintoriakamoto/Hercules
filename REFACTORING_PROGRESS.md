# Hercules Architecture Refactoring Progress

## Status: IN PROGRESS

### Phase 1: Foundation (Transport & Compression Unification)
- [ ] **1.1** Create unified transport interface (no None fallback)
- [ ] **1.2** Consolidate provider logic (eliminate duplicate code)
- [ ] **1.3** Unify compression stack (strategy pattern)
- [ ] **1.4** Add telemetry for migration tracking

### Phase 2: Critical Infrastructure  
- [ ] **2.1** Plugin integrity (signatures + capabilities)
- [ ] **2.2** Web content trust boundary
- [ ] **2.3** CLI circular dependency resolution

### Phase 3: Structural Refactoring
- [ ] **3.1** Extract gateway adapters to dedicated layer
- [ ] **3.2** Decompose god files (main.py, web_server.py, gateway/run.py)

---

## Implementation Notes

Each commit will:
1. Preserve backwards compatibility (when possible)
2. Add comprehensive tests
3. Update telemetry/logging
4. Document migration path

Branch: `claude/hacker-pentest-agent-specs-1ame05`
