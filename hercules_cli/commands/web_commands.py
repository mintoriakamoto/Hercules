"""Web server and dashboard commands.

Handles:
  - Starting web server
  - Dashboard management
  - HTTP API configuration
  - WebSocket management

Extracted from main.py:cmd_web_* handlers (~2.5k lines)
"""

from __future__ import annotations

import argparse
import logging

logger = logging.getLogger(__name__)


def add_web_subcommands(subparsers: argparse._SubParsersAction) -> None:
    """Register web server subcommands."""
    web_parser = subparsers.add_parser(
        "web",
        help="Web server and dashboard",
    )
    web_subparsers = web_parser.add_subparsers(dest="web_cmd")

    # Start server
    start_parser = web_subparsers.add_parser(
        "start",
        help="Start web server",
    )
    start_parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    start_parser.add_argument("--host", default="localhost", help="Host to bind to")
    start_parser.set_defaults(func=handle_web_start)

    # Stop server
    stop_parser = web_subparsers.add_parser(
        "stop",
        help="Stop web server",
    )
    stop_parser.set_defaults(func=handle_web_stop)

    # Dashboard
    dashboard_parser = web_subparsers.add_parser(
        "dashboard",
        help="Manage dashboard",
    )
    dashboard_subparsers = dashboard_parser.add_subparsers(dest="dashboard_cmd")

    dash_open = dashboard_subparsers.add_parser("open", help="Open dashboard in browser")
    dash_open.set_defaults(func=handle_dashboard_open)

    dash_config = dashboard_subparsers.add_parser("config", help="Configure dashboard")
    dash_config.add_argument("setting", help="Setting name")
    dash_config.add_argument("value", help="Setting value")
    dash_config.set_defaults(func=handle_dashboard_config)


def handle_web_start(args: argparse.Namespace) -> None:
    """Handle 'hercules web start' command."""
    logger.info("Starting web server on %s:%d", args.host, args.port)
    # Implementation will be filled in


def handle_web_stop(args: argparse.Namespace) -> None:
    """Handle 'hercules web stop' command."""
    logger.info("Stopping web server")
    # Implementation will be filled in


def handle_dashboard_open(args: argparse.Namespace) -> None:
    """Handle 'hercules web dashboard open' command."""
    logger.info("Opening dashboard in browser")
    # Implementation will be filled in


def handle_dashboard_config(args: argparse.Namespace) -> None:
    """Handle 'hercules web dashboard config' command."""
    logger.info("Configuring dashboard: %s=%s", args.setting, args.value)
    # Implementation will be filled in
