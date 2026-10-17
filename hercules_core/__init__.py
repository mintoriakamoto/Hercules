"""Hercules core - shared types and utilities for agent/tools/gateway and CLI.

This module provides the interface layer that breaks the circular dependency
between the core (agent/, tools/, gateway/) and CLI (hercules_cli/).

Both can import from here without creating import cycles.
"""

__version__ = "1.0"
