"""``hercules hermes`` — local agent mesh scan.

Not wired from main.py yet (god-file). Use:
  python -m hercules_cli.hermes
Doctor also prints the mesh.
"""

from __future__ import annotations

from typing import Callable


def build_hermes_parser(subparsers, *, cmd_hermes: Callable) -> None:
    parser = subparsers.add_parser(
        "hermes",
        help="Scan local agents/frameworks and list the Hermes mesh",
        description="Find .claude .opencode .openclaw .langchain pip/venv agents",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable")
    parser.set_defaults(func=cmd_hermes)
