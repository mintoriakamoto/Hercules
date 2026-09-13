"""CLI command modules.

Refactored from monolithic main.py to separate concerns by domain.
Each module handles one category of commands and remains under 3k lines.

Modules:
  - agent_commands: agent execution, conversation, model switching
  - auth_commands: login, logout, token management
  - web_commands: web server, dashboard
  - config_commands: configuration, settings
  - mesh_commands: mesh networking, cluster operations
"""

from hercules_cli.commands.agent_commands import add_agent_subcommands
from hercules_cli.commands.auth_commands import add_auth_subcommands
from hercules_cli.commands.config_commands import add_config_subcommands
from hercules_cli.commands.mesh_commands import add_mesh_subcommands
from hercules_cli.commands.web_commands import add_web_subcommands

# Phase 3C: Re-export gateway command definitions from legacy commands module
# When gateway/run.py imports from hercules_cli.commands, it gets this package.
# We need to re-export the legacy command registry that gateway expects.
import sys
import importlib.util

# Try to get the legacy module (commands.py) that's being shadowed by this package
spec = importlib.util.spec_from_file_location(
    "hercules_cli._legacy_commands",
    __file__.replace('/commands/__init__.py', '/commands.py')
)
_legacy_commands = importlib.util.module_from_spec(spec)
# Register in sys.modules BEFORE executing so dataclass decorators work
sys.modules["hercules_cli._legacy_commands"] = _legacy_commands
spec.loader.exec_module(_legacy_commands)

# Re-export what gateway.run expects
GATEWAY_KNOWN_COMMANDS = _legacy_commands.GATEWAY_KNOWN_COMMANDS
is_gateway_known_command = _legacy_commands.is_gateway_known_command
resolve_command = _legacy_commands.resolve_command

__all__ = [
    "add_agent_subcommands",
    "add_auth_subcommands",
    "add_config_subcommands",
    "add_mesh_subcommands",
    "add_web_subcommands",
    "GATEWAY_KNOWN_COMMANDS",
    "is_gateway_known_command",
    "resolve_command",
]
