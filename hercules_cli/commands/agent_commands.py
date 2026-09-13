"""Agent execution commands.

Handles:
  - Starting an agent
  - Running conversations
  - Model and provider switching
  - Context management
  - Tool execution control

Extracted from main.py:cmd_agent_* handlers (~2.5k lines)
"""

from __future__ import annotations

import argparse
import logging
from typing import Any

logger = logging.getLogger(__name__)


def add_agent_subcommands(subparsers: argparse._SubParsersAction) -> None:
    """Register agent-related subcommands.

    Expected commands:
      - cmd_agent_start: Start an agent
      - cmd_agent_run: Run a single turn
      - cmd_agent_switch_model: Switch to different model
      - cmd_agent_switch_provider: Switch provider
    """
    agent_parser = subparsers.add_parser(
        "agent",
        help="Agent execution and control",
    )
    agent_subparsers = agent_parser.add_subparsers(dest="agent_cmd")

    # Start
    start_parser = agent_subparsers.add_parser(
        "start",
        help="Start an agent session",
    )
    start_parser.add_argument("--model", help="Model to use")
    start_parser.add_argument("--provider", help="Provider to use")
    start_parser.set_defaults(func=handle_agent_start)

    # Run
    run_parser = agent_subparsers.add_parser(
        "run",
        help="Run a single agent turn",
    )
    run_parser.add_argument("message", help="User message")
    run_parser.set_defaults(func=handle_agent_run)

    # Switch model
    model_parser = agent_subparsers.add_parser(
        "switch-model",
        help="Switch to a different model",
    )
    model_parser.add_argument("model_name", help="Model name to switch to")
    model_parser.set_defaults(func=handle_agent_switch_model)

    # Switch provider
    provider_parser = agent_subparsers.add_parser(
        "switch-provider",
        help="Switch to a different provider",
    )
    provider_parser.add_argument("provider", help="Provider (anthropic, openai, bedrock)")
    provider_parser.set_defaults(func=handle_agent_switch_provider)


async def handle_agent_start(args: argparse.Namespace) -> None:
    """Handle 'hercules agent start' command."""
    logger.info("Starting agent: model=%s, provider=%s", args.model, args.provider)
    # Implementation will be filled in during migration


async def handle_agent_run(args: argparse.Namespace) -> None:
    """Handle 'hercules agent run' command."""
    logger.info("Running agent turn: %s", args.message)
    # Implementation will be filled in during migration


async def handle_agent_switch_model(args: argparse.Namespace) -> None:
    """Handle 'hercules agent switch-model' command."""
    logger.info("Switching model to: %s", args.model_name)
    # Implementation will be filled in during migration


async def handle_agent_switch_provider(args: argparse.Namespace) -> None:
    """Handle 'hercules agent switch-provider' command."""
    logger.info("Switching provider to: %s", args.provider)
    # Implementation will be filled in during migration
