"""Type definitions for Hercules - no runtime imports to avoid cycles."""

from typing import Dict, Any, Optional, List
from pathlib import Path


class Config:
    """Configuration container - used by both core and CLI."""
    pass


class SessionContext:
    """Session context - used by both core and CLI."""
    session_key: str
    profile: Optional[str] = None
    

class PluginInfo:
    """Plugin metadata."""
    name: str
    path: Path
    enabled: bool


# Type aliases for lazy imports
ConfigLoadFn = callable
PluginDiscoveryFn = callable
