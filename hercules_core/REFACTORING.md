# Circular Dependency Refactoring Path

## Current State
- agent/, tools/, gateway/ ← hercules_cli/config.py (206 imports)
- hercules_cli/ → agent/, tools/, gateway/ (456 imports total)
- **Result**: Masked by 408 lazy imports in hercules_cli/config.py

## Solution: hercules_core/ Layer

### Phase 1: Extract Type Definitions ✓
- hercules_core/types.py - Configuration, Session, Plugin types
- hercules_core/__init__.py - Package skeleton

### Phase 2: Extract Utilities (Next)
Core modules should import from hercules_core instead of hercules_cli:
```python
# OLD (creates cycle):
from hercules_cli.config import load_config

# NEW (breaks cycle):  
from hercules_core.lazy import get_load_config
config = get_load_config()()  # Lazy import at call time
```

### Phase 3: Migrate Imports
Update these to use hercules_core:
- agent/*.py - Remove hercules_cli.config imports
- tools/*.py - Remove hercules_cli.config imports  
- gateway/*.py - Remove hercules_cli imports

### Phase 4: Verify No Cycles
```bash
pip install pipdeptree
python -m pipdeptree --warn fail hercules_core
```

## Why This Works
- hercules_core has NO runtime imports
- Types are lightweight (no side effects)
- Lazy loaders defer imports until needed
- Both core and CLI import from hercules_core
- Cycle is broken: hercules_core ← core, CLI ← hercules_core (no back-edge)

## Implementation Notes
- Keep functions in hercules_cli, just move signatures
- Use TYPE_CHECKING guards for forward refs
- Add deprecation warnings to old hercules_cli imports
- Update CLAUDE.md once complete
