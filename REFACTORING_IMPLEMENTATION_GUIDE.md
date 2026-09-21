# Hercules Architecture Refactoring - Implementation Guide

## Overview

This guide provides step-by-step implementation instructions for completing all 8 architectural improvements to Hercules. Foundation work has been completed; this document covers integration, testing, and full rollout.

**Status:** Phase 1 foundation + Phase 2 infrastructure complete. Ready for integration.

---

## Phase 1: Transport & Compression (Foundation) ✅ COMPLETE

### 1.1 Unified Compression Integration

**Status:** ✅ Compression strategy interface implemented

**Next Steps:**
1. Integrate `agent/compression_strategy.py` into `agent/conversation_loop.py`
   - Replace 4 overlapping compressor calls with single `Compressor` instance
   - Use configurable strategy (default: "balanced")
   - Collect metrics per turn

**File:** `agent/conversation_loop.py` (~line 455)

```python
# BEFORE (scattered):
trajectory_compressor.compress(trajectory)
context_compressor.compress(context)
summary_compressor.compress(summary)

# AFTER (unified):
from agent.compression_strategy import Compressor, StrategyFactory

compressor = Compressor(strategy="balanced", enable_metrics=True)
compressed_trajectory = compressor.compress(trajectory, max_tokens=8000, content_type="trajectory")
compressed_context = compressor.compress(context, max_tokens=4000, content_type="context")
```

**Tests:**
- `tests/agent/test_compression_strategy.py` - test strategy implementations
- `tests/agent/test_unified_compression.py` - test integration with loop

---

### 1.2 Transport Fallback Mode Implementation

**Status:** ✅ Unified transport factory implemented

**Next Steps:**
1. Update `agent/transports/__init__.py` to use `FallbackMode`
2. Replace silent `None` fallback with explicit exception or feature flag
3. Add telemetry emission to track fallback usage

**File:** `agent/transports/__init__.py`

```python
# NEW IMPORT
from agent.transports.unified import TransportFactory, FallbackMode

# Update get_transport to use factory
_factory = TransportFactory(fallback_mode=FallbackMode.TRY_LEGACY)

def get_transport(api_mode: str):
    """Get transport with explicit fallback handling."""
    return _factory.get_transport(api_mode)

# Emit fallback stats on shutdown
def emit_migration_metrics():
    stats = _factory.get_fallback_stats()
    for api_mode, count in stats.items():
        logger.warning(f"Transport {api_mode} fell back {count} times")
```

**Tests:**
- `tests/agent/transports/test_unified.py` - test fallback modes
- `tests/agent/transports/test_provider_dispatch.py` - test all providers

---

### 1.3 Consolidate Provider Logic

**Status:** ⏳ NEXT: Merge auxiliary_client.py into transports

**Steps:**
1. Extract provider logic from `auxiliary_client.py` (6.9k lines)
2. Identify duplication with `agent/chat_completion_helpers.py`
3. Create unified provider interface in `agent/transports/`
4. Deprecate `auxiliary_client.py` after migration

**Duplicate locations:**
- `auxiliary_client.py:sync_provider_stack()` vs `chat_completion_helpers.py:_dispatch_nonstreaming_api_request()`
- `auxiliary_client.py:async_provider_stack()` vs transports layer

**Consolidation strategy:**
```python
# agent/transports/provider.py (NEW)
class ProviderDispatcher:
    """Unified provider dispatch for all contexts."""
    
    async def dispatch(self, api_mode: str, request: Dict) -> Response:
        """Single entry point for provider requests."""
        transport = get_transport(api_mode)
        return await transport.send(request)

# Replace both paths:
# - chat_completion_helpers.py → uses ProviderDispatcher
# - auxiliary_client.py → uses ProviderDispatcher (then deprecate)
```

---

## Phase 2: Critical Infrastructure (Partial Complete)

### 2.1 Plugin Integrity Integration ✅ IMPLEMENTED

**Status:** ✅ Plugin integrity system implemented

**Integration Steps:**
1. Load plugin manifests at startup
2. Verify each plugin before `exec_module()`
3. Cache verified capabilities in CapabilityAuditor

**File:** `tools/registry.py` (~line 50)

```python
from agent.plugin_integrity import PluginIntegrityManager

integrity_manager = PluginIntegrityManager(
    manifest_path=Path.home() / ".hercules" / "plugins.json",
    signing_key=load_signing_key(),  # Ed25519 public key
)

def load_plugin(plugin_path: Path, plugin_name: str):
    """Load plugin with integrity verification."""
    try:
        # Verify plugin
        manifest = integrity_manager.verify_plugin(plugin_path, plugin_name)
        
        # Get capabilities
        capabilities = integrity_manager.auditor.approvals.get(plugin_name, set())
        
        # Load plugin
        spec = importlib.util.spec_from_file_location("plugin", plugin_path / "__init__.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        return module
    except IntegrityError as e:
        logger.error(f"Plugin integrity check failed: {e}")
        raise
```

**Tests:**
- `tests/agent/test_plugin_integrity.py`
- `tests/tools/test_registry_with_integrity.py`

---

### 2.2 Web Content Trust Boundary ✅ IMPLEMENTED

**Status:** ✅ Content approval system implemented

**Integration Steps:**
1. Import `ContentApprovalManager` in approval pipeline
2. Wrap all web fetches with `request_approval()`
3. Check hash before reusing old approvals

**File:** `tools/approval.py` (~line 100)

```python
from agent.content_trust import ContentApprovalManager, ContentSource

approval_mgr = ContentApprovalManager(
    approval_log_path=Path.home() / ".hercules" / "approvals.json"
)

def approval_required(action, content: str):
    """Check if action needs approval."""
    # Get content source
    source = ContentSource.WEB_FETCH if action.from_web else ContentSource.AGENT_COMMAND
    
    # Request approval
    approval = approval_mgr.request_approval(
        action_type=action.type,
        content=content,
        content_source=source,
    )
    
    # If previously approved and content unchanged, reuse
    if approval.user_approved:
        return True
    
    # Otherwise, gate with user approval
    return get_user_approval(approval)
```

**Tests:**
- `tests/agent/test_content_trust.py`
- `tests/tools/test_approval_with_content_trust.py`

---

### 2.3 CLI Circular Dependency Resolution ⏳ STARTED

**Status:** ⏳ Core API layer created, integration pending

**Integration Steps:**
1. **Update imports in run_agent.py**
   - Replace `from hercules_cli.config import ...` with `from hercules_agent.core_api import AgentConfig`
   - Keep CLI-specific config in `hercules_cli/config_ui.py`

2. **Create config migration layer**
   ```python
   # hercules_cli/config_adapter.py (NEW)
   def cli_config_to_agent_config(cli_config: CliConfig) -> AgentConfig:
       """Convert CLI config to core API config."""
       return AgentConfig(
           model_name=cli_config.model,
           provider_mode=ProviderMode(cli_config.api_mode),
           # ... other fields
       )
   ```

3. **Update main.py to use commands modules**
   ```python
   # hercules_cli/main.py (refactored)
   from hercules_cli.commands import (
       agent_commands,
       auth_commands,
       web_commands,
       config_commands,
       mesh_commands,
   )
   
   def main():
       parser = argparse.ArgumentParser()
       subparsers = parser.add_subparsers()
       
       agent_commands.add_agent_subcommands(subparsers)
       auth_commands.add_auth_subcommands(subparsers)
       web_commands.add_web_subcommands(subparsers)
       config_commands.add_config_subcommands(subparsers)
       mesh_commands.add_mesh_subcommands(subparsers)
   ```

**Expected Outcome:**
- Remove 206 imports of config.py from core modules
- Break `run_agent.py` → `hercules_cli` cycle
- Enable parallel tests (pytest directory-level)

**Tests:**
- `tests/hercules_cli/test_main_with_commands.py`
- `tests/hercules_cli/test_config_adapter.py`

---

## Phase 3: Structural Refactoring

### 3.1 Extract Gateway Adapters ⏳ NEXT

**Status:** ⏳ Platform manager created, adapter migration pending

**Implementation:**
1. Move platform adapters from `plugins/platforms/*` to `gateway/platforms/*/handler.py`
2. Update platform manager to load from new location
3. Keep plugins/platforms/ structure with deprecation warning

**File Migration:**
```
BEFORE:
plugins/platforms/telegram/adapter.py (8.8k) ← messaging gateway
plugins/platforms/discord/adapter.py (8.4k)  ← messaging gateway

AFTER:
gateway/platforms/telegram/handler.py (8.8k)
gateway/platforms/discord/handler.py (8.4k)
gateway/platforms/feishu/handler.py (5.7k)
```

**Integration:**
```python
# gateway/run.py (refactored)
from gateway.platform_manager import PlatformManager

platform_manager = PlatformManager()
await platform_manager.load_from_config(Path("gateway/platforms.json"))
await platform_manager.start()
```

**Benefits:**
- Reduces conceptual load of plugins/ (105k → ~15k)
- Clarifies gateway is message routing, not tools
- Single source of truth for platform management

---

### 3.2 Decompose God Files ⏳ NEXT

**Status:** ⏳ Command module structure created

**Implementation:**

#### main.py (14.7k → 3k)
Move handlers to `hercules_cli/commands/*`:
- `cmd_agent_*` → `agent_commands.py`
- `cmd_login_*`, `cmd_logout_*` → `auth_commands.py`
- `cmd_web_*` → `web_commands.py`
- `cmd_config_*` → `config_commands.py`
- `cmd_mesh_*` → `mesh_commands.py`

#### gateway/run.py (21k → 8k)
Separate by responsibility:
- Platform lifecycle → `gateway/platform_manager.py` ✅ Done
- Message routing → `gateway/message_router.py`
- Event handlers → `gateway/event_handlers.py`
- Configuration → `gateway/gateway_config.py`

#### web_server.py (17k → 5k)
Extract routes:
- `hercules_cli/web/routes/auth.py` (auth endpoints)
- `hercules_cli/web/routes/agent.py` (agent endpoints)
- `hercules_cli/web/routes/kanban.py` (kanban endpoints)
- `hercules_cli/web/routes/config.py` (config endpoints)

**Pattern for each module:**
- Max 3k lines
- Single domain responsibility
- Clear dependencies (dependency injection)
- Comprehensive tests (>80% coverage)

---

## Testing Strategy

### Unit Tests
Each new module needs comprehensive unit tests:
- Happy path
- Error cases
- Edge cases
- Configuration variations

### Integration Tests
End-to-end tests for refactored flows:
- Plugin loading with integrity checks
- Transport fallback modes
- CLI command execution
- Gateway platform startup

### Regression Tests
Ensure existing functionality unaffected:
- Run full test suite: `scripts/run_tests.sh`
- Performance benchmarks (compression ratios, latency)
- Cross-platform testing (Telegram, Discord, Feishu)

### Example Test Structure
```python
# tests/agent/test_compression_strategy.py
import pytest
from agent.compression_strategy import (
    Compressor,
    BalancedCompression,
    CompressionMetrics,
)

def test_balanced_compression_reduces_size():
    compressor = Compressor(strategy="balanced")
    content = "x" * 100000
    compressed = compressor.compress(content, max_tokens=1000)
    assert len(compressed) < len(content)

def test_compression_metrics_tracked():
    compressor = Compressor(strategy="balanced", enable_metrics=True)
    compressor.compress("hello world", max_tokens=1000, content_type="test")
    metrics = compressor.get_metrics()
    assert len(metrics) == 1
    assert metrics[0].content_type == "test"
```

---

## Rollout Strategy

### Phase 1: Experimental (1 week)
- Merge on feature branch
- Enable via feature flags
- Production disabled

### Phase 2: Staged (2 weeks)
- Enable for 10% of sessions
- Monitor error rates and latency
- Gradual increase to 50%

### Phase 3: Full Rollout (1 week)
- Enable for all sessions
- Disable old code paths
- Deprecate legacy modules

### Rollback Plan
- Each change feature-flagged
- Old implementations remain (3 month deprecation window)
- Instant disable if issues detected

---

## Metrics & Monitoring

### Success Metrics
| Metric | Target | Baseline |
|--------|--------|----------|
| Max file size | <5k lines | 21k lines |
| Circular dependencies | 0 | 456 imports |
| Test parallelization | No pollution | 225 failures |
| Plugin security coverage | 100% | 0% |
| Content trust coverage | 100% | 0% |
| Compression ratio | >30% avg | varies |

### Telemetry Events
- `transport.fallback_legacy` - migration tracking
- `compression.completed` - compression performance
- `plugin.verified` - security verification
- `approval.granted` - content approval gates

---

## Dependencies & Prerequisites

### Required Libraries
- `nacl` (PyNaCl) - for Ed25519 signature verification
- `asyncio` - for async platform handlers

### Installation
```bash
pip install PyNaCl  # Plugin signature verification
```

### Configuration Files

**plugins.json** (~/.hercules/plugins.json)
```json
{
  "telegram": {
    "name": "telegram",
    "version": "1.0.0",
    "content_hash": "sha256:...",
    "signature": "ed25519:...",
    "capabilities": ["message.receive", "message.send"],
    "description": "Telegram message adapter"
  }
}
```

**platforms.json** (gateway/platforms.json)
```json
{
  "telegram": {
    "type": "telegram",
    "enabled": true,
    "api_token": "${TELEGRAM_API_TOKEN}",
    "webhook_url": "https://example.com/webhooks/telegram"
  }
}
```

---

## Risk Mitigation

### High Risk: Transport Migration
- **Risk:** Breaking provider dispatch
- **Mitigation:** Feature flags per provider, canary rollout, comprehensive tests

### Medium Risk: Plugin Integrity
- **Risk:** Legitimate plugins rejected
- **Mitigation:** Deprecation window, signature generation tools, clear error messages

### Medium Risk: CLI Refactor
- **Risk:** Command lookup failures
- **Mitigation:** Comprehensive CLI tests, command registry validation

---

## Timeline Estimate

| Phase | Duration | Effort | Risk |
|-------|----------|--------|------|
| 1: Transport/Compression | 2 weeks | 10 days | High |
| 2: Plugin/Content/CLI | 2 weeks | 10 days | High |
| 3: Gateway/God files | 2 weeks | 10 days | Medium |
| **Testing & Polish** | 2 weeks | 10 days | Low |
| **Total** | **8 weeks** | **40 days** | - |

---

## Handoff Checklist

- [ ] All code reviewed
- [ ] Tests pass (>80% coverage)
- [ ] Documentation updated
- [ ] Feature flags configured
- [ ] Rollback procedure tested
- [ ] Team trained on new architecture
- [ ] Monitoring/telemetry validated
- [ ] Performance regression tested

---

## Questions & Next Steps

1. **Signing Key Management:** How should Ed25519 keys be managed/distributed?
2. **Manifest Generation:** Automated manifest generation at build time?
3. **Backwards Compatibility:** How long to support legacy transports?
4. **Feature Flag System:** Use environment variables vs. config file?

---

## Contacts

- Architecture Lead: [TBD]
- Transport Lead: [TBD]
- CLI Lead: [TBD]
- Testing Lead: [TBD]
