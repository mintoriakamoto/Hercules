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

# Re-export what gateway.run and other modules expect from legacy commands.py
# These are accessed from many places in the gateway and CLI infrastructure
GATEWAY_KNOWN_COMMANDS = _legacy_commands.GATEWAY_KNOWN_COMMANDS
is_gateway_known_command = _legacy_commands.is_gateway_known_command
resolve_command = _legacy_commands.resolve_command
gateway_help_lines = _legacy_commands.gateway_help_lines
COMMANDS = _legacy_commands.COMMANDS
COMMANDS_BY_CATEGORY = _legacy_commands.COMMANDS_BY_CATEGORY
COMMAND_REGISTRY = _legacy_commands.COMMAND_REGISTRY
ACTIVE_SESSION_BYPASS_COMMANDS = _legacy_commands.ACTIVE_SESSION_BYPASS_COMMANDS
should_bypass_active_session = _legacy_commands.should_bypass_active_session
telegram_menu_commands = _legacy_commands.telegram_menu_commands
telegram_menu_max_commands = _legacy_commands.telegram_menu_max_commands
SlashCommandCompleter = _legacy_commands.SlashCommandCompleter
discord_skill_commands_by_category = _legacy_commands.discord_skill_commands_by_category
slack_native_slashes = _legacy_commands.slack_native_slashes
slack_subcommand_map = _legacy_commands.slack_subcommand_map
slack_app_manifest = _legacy_commands.slack_app_manifest
_sanitize_telegram_name = _legacy_commands._sanitize_telegram_name
_file_size_label = _legacy_commands._file_size_label
_is_gateway_available = _legacy_commands._is_gateway_available
_resolve_config_gates = _legacy_commands._resolve_config_gates
_iter_plugin_command_entries = _legacy_commands._iter_plugin_command_entries

__all__ = [
    # Modular command registration (new structure)
    "add_agent_subcommands",
    "add_auth_subcommands",
    "add_config_subcommands",
    "add_mesh_subcommands",
    "add_web_subcommands",
    # Gateway and command infrastructure (legacy module re-exports)
    "GATEWAY_KNOWN_COMMANDS",
    "is_gateway_known_command",
    "resolve_command",
    "gateway_help_lines",
    "COMMANDS",
    "COMMANDS_BY_CATEGORY",
    "COMMAND_REGISTRY",
    "ACTIVE_SESSION_BYPASS_COMMANDS",
    "should_bypass_active_session",
    "telegram_menu_commands",
    "telegram_menu_max_commands",
    "SlashCommandCompleter",
    "discord_skill_commands_by_category",
    "slack_native_slashes",
    "slack_subcommand_map",
    "slack_app_manifest",
    "_sanitize_telegram_name",
    "_file_size_label",
    "_is_gateway_available",
    "_resolve_config_gates",
    "_iter_plugin_command_entries",
]
