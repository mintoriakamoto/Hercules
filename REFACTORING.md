# HERCULES GOD FILES DECOMPOSITION REFACTORING

**Objective**: Reduce 62.3% of codebase in oversized files (>1500 lines) to modular, maintainable structure.

**Scope**: 6 critical god files totaling ~100k lines → 20+ focused modules (4-5k lines each)

---

## FILES TO DECOMPOSE

### 1. gateway/run.py (22,717 lines) — HIGHEST PRIORITY
**Target**: 5-6 modules

- **gateway/voice.py** (~800 lines) - Voice/TTS management
- **gateway/session_manager.py** (~2k lines) - Session routing, agent resolution
- **gateway/telegram.py** (~1.5k lines) - Telegram-specific logic
- **gateway/platform.py** (~1k lines) - Platform adapter lifecycle
- **gateway/lifecycle.py** (~1k lines) - Exit handling, shutdown, scale-to-zero
- **gateway/run.py** (~5k lines) - GatewayRunner orchestrator (imports from above)

**Effort**: 4-5 days | **Risk**: Medium (core daemon) | **Testing**: Full integration test suite

---

### 2. hercules_cli/web_server.py (17,866 lines)
**Target**: 3-4 modules

- **hercules_cli/web/dashboard.py** (~6k lines) - Dashboard UI endpoints
- **hercules_cli/web/api.py** (~5k lines) - REST API endpoints
- **hercules_cli/web/static.py** (~2k lines) - Static file serving
- **hercules_cli/web_server.py** (~4.8k lines) - Server orchestrator

**Effort**: 3-4 days | **Risk**: Low (UI layer) | **Testing**: API/UI integration tests

---

### 3. hercules_cli/main.py (15,207 lines)
**Target**: 4-5 modules

Analyze structure first to determine split points.
- Likely: commands/, handlers/, config/, utils/
- Estimate: 2-3 days

**Risk**: High (entry point) | **Testing**: CLI test suite

---

### 4. cli.py (16,904 lines) — VERIFY FIRST
**Target**: Determine if duplicate, then remove or consolidate

**Investigation needed**:
- Is this deprecated in favor of hercules_cli/main.py?
- Any code NOT in main.py?
- Safe to delete?

**Effort**: 1-2 days analysis | **Risk**: High if not dead code

---

### 5. agent/auxiliary_client.py (7,682 lines) — MIGRATION IN PROGRESS
**Target**: Remove entirely (migrate to agent/transports/)

**Status**: New transports/ exists but old auxiliary_client still in use

**Effort**: 2-3 days (finish migration) | **Risk**: High (core RPC)

---

### 6. hercules_cli/config.py (8,787 lines)
**Target**: 2-3 modules

This is most-imported module (206+ inbound). Must be careful.

- **hercules_cli/config/core.py** (~3k) - Core config classes
- **hercules_cli/config/loader.py** (~3k) - Config loading logic
- **hercules_cli/config/validation.py** (~2.7k) - Validation
- **hercules_cli/config.py** - Re-exports for backward compatibility

**Effort**: 2-3 days | **Risk**: CRITICAL (inverted dependency - CLI config imported everywhere)

---

## IMPLEMENTATION SEQUENCE

### Phase 1: Gateway (5-6 days)
1. gateway/run.py decomposition
2. Full gateway integration testing
3. Deploy & monitor

### Phase 2: CLI Web Server (3-4 days)
1. hercules_cli/web_server.py decomposition
2. API/UI testing
3. Deploy

### Phase 3: Investigation & Decision (1-2 days)
1. Analyze cli.py vs hercules_cli/main.py
2. Decide: delete or consolidate?
3. Propose to owner

### Phase 4: Transport Layer Migration (2-3 days)
1. Finish agent/transports/ migration
2. Remove agent/auxiliary_client.py
3. Update all imports
4. RPC integration testing

### Phase 5: Core CLI (2-3 days)
1. hercules_cli/main.py analysis
2. Design split points
3. Decompose
4. CLI test suite

### Phase 6: Config Layer (2-3 days)
1. hercules_cli/config.py decomposition
2. Maintain backward-compatible re-exports
3. Test all 206+ import sites
4. Verify no circular dependencies introduced

---

## ARCHITECTURAL PRINCIPLES

**During refactoring, maintain**:
- YOLO design (no new restrictions/gates added)
- Inverted approval logic
- Existing API contracts
- Module import paths (use re-exports if needed)

**Avoid**:
- Creating new circular dependencies
- Breaking backward compatibility
- Adding security restrictions
- Changing behavioral semantics

---

## TESTING STRATEGY

Each phase includes:
- **Unit tests** for new modules
- **Integration tests** for composition
- **Regression tests** against existing test suite
- **Load testing** for gateway (high throughput)
- **Manual smoke tests** of user-facing features

---

## ESTIMATED TOTAL EFFORT

- **Sequence**: 19-23 days (5-6 week part-time)
- **Can parallelize**: Phases 1 & 2 somewhat independent
- **Critical path**: Phase 1 (gateway) + Phase 6 (config)

---

## SUCCESS METRICS

- ✅ All files <5k lines (except orchestrator classes)
- ✅ Zero new circular dependencies
- ✅ All existing tests pass
- ✅ No new security gates added
- ✅ YOLO design fully preserved
- ✅ Easier to understand, test, refactor

---

## NOTES

- Phase 3 (cli.py investigation) may accelerate if delete is safe
- Phase 4 (transports) blocks Phase 5 (CLI) if CLI uses auxiliary_client
- Phase 6 (config) is critical - 206 import sites means high risk
- Start with Phase 1 (gateway/run.py) - highest ROI, good learning for other phases
