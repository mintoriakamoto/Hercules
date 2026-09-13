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

from hercules_cli.commands import (
    agent_commands,
    auth_commands,
    config_commands,
    mesh_commands,
    web_commands,
)

__all__ = [
    "agent_commands",
    "auth_commands",
    "config_commands",
    "mesh_commands",
    "web_commands",
]
