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

__all__ = [
    "add_agent_subcommands",
    "add_auth_subcommands",
    "add_config_subcommands",
    "add_mesh_subcommands",
    "add_web_subcommands",
]
