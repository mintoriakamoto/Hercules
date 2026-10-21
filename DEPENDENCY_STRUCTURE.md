# Dependency Structure & Tiering

## Overview

Hercules now uses **explicit dependency tiers** to prevent import chains from breaking the system when optional packages are unavailable.

### Tier Hierarchy

```
core (required)
  ↓
execution (stdlib + core)
  ↓
gateway (integration layer, requires httpx)
  ↓
integrations (platform adapters)
```

## Tier Definitions

### Core Tier
**Location**: `agent/core/`, `agent/execution/`, `agent/schema/`, `agent/dependency_injection.py`

**Dependencies**:
- `anthropic` - AI model API
- `pydantic` - Data validation
- Python stdlib (asyncio, json, time, etc.)

**Guarantee**: Works without any optional packages. Can be imported and used immediately.

```python
from agent.execution.fast_inference import InferenceCache
from agent.execution.tool_batching import ParallelToolExecutor
# Always works, no external deps needed
```

### Execution Tier
**Location**: `agent/execution/`, `agent/compression/`, `agent/ensemble/`, `agent/routing/`, `agent/meta/`, `agent/memory/`, `agent/knowledge/`

**Dependencies**:
- Everything from core
- Stdlib only (no external packages)

**Guarantee**: All inference, tool execution, and context operations work without platform integrations.

### Gateway Tier
**Location**: `agent/auth_provider.py`, `gateway/` adapters

**Dependencies**:
- Everything from execution
- `httpx` - Platform authentication
- Platform SDKs (lazy-loaded via DependencyContainer)

**Guarantee**: Gracefully degrades if optional packages unavailable.

### Integrations Tier
**Location**: `plugins/platforms/*/`, platform-specific code

**Dependencies**:
- Everything from gateway
- Platform-specific SDKs (Slack, Discord, etc.)

**Guarantee**: Each integration is independently optional.

## Dependency Injection

### Pattern 1: Optional Dependency

```python
from agent.dependency_injection import DependencyContainer, requires_dependency

@requires_dependency("httpx", tier="gateway")
def create_client(_dep=None):
    """httpx is injected automatically."""
    return _dep.Client()
```

### Pattern 2: Graceful Fallback

```python
httpx = DependencyContainer.get("httpx")
if httpx is None:
    logger.info("httpx not available, using default client")
    client = create_default_client()
else:
    client = httpx.Client()
```

### Pattern 3: Required Dependency

```python
anthropic = DependencyContainer.get("anthropic", required=True)
# Raises ImportError if not available
```

## Forbidden Imports

The manifest file `.dependency-manifest.json` defines forbidden import combinations to prevent breaking the tiering:

```json
{
  "forbidden_imports": {
    "agent.core": ["httpx", "slack_sdk", "discord"],
    "agent.execution": ["httpx", "hercules_cli"],
    "agent.compression": ["hercules_cli.auth"]
  }
}
```

These are validated by:
- Pre-commit hooks (before commit)
- `scripts/validate_dependencies.py` (in CI)
- Unit tests in `tests/test_dependency_structure.py`

## Migration Guide

### For Code Using `httpx` or Other Optional Deps

**Before:**
```python
import httpx
from hercules_cli import auth

def create_client():
    return httpx.Client(headers=auth.get_headers())
```

**After:**
```python
from agent.auth_provider import get_auth_provider

def create_client():
    provider = get_auth_provider()
    return provider.create_authenticated_client()
```

### For New Modules

1. Check the tier where your code lives
2. Only import from same tier or lower
3. For optional dependencies, use `DependencyContainer.get()`
4. Run validation: `python scripts/validate_dependencies.py`

## Validation

### Local
```bash
# Run dependency validation
python scripts/validate_dependencies.py

# Run tests
python -m pytest tests/test_dependency_structure.py -v

# Check pre-commit hooks
pre-commit run --all-files
```

### CI
The following run automatically on every commit:
- `dependency-check`: Validates tier structure
- `forbidden-imports`: Checks forbidden import list
- `jsonschema-validation`: Ensures schemas are valid

## Benefits

### Before (Current)
- ✗ Import `agent.compression` → fails if httpx not installed
- ✗ CI Pylint crashes on optional dependencies
- ✗ Circular dependencies hard to debug
- ✗ Unclear what depends on what

### After (With Tiers)
- ✓ Core always works regardless of installed packages
- ✓ CI Pylint runs without `--extra all`
- ✓ Clear, compile-time-verified dependency graph
- ✓ Graceful degradation for optional features

## Expected Improvements

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| **CI Pylint time** | Fails | 2-3 minutes | ✓ Passes |
| **Core package dependencies** | Unknown | ~5 (anthropic, pydantic + stdlib) | Clarity |
| **Forbidden imports caught** | 0 | 100% (pre-commit) | Safety |
| **Import depth** | ~6 (core→auth→httpx) | ~2 (core→di→lazy-load) | Simplicity |

## Questions?

See:
- `.dependency-manifest.json` - Full dependency manifest
- `agent/dependency_injection.py` - DI container implementation
- `FAST_INFERENCE_GUIDE.md` - Integration examples
- `tests/test_dependency_structure.py` - Validation tests
