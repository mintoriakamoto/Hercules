"""``hercules mesh`` — local agent mesh scan.

Not wired from main.py yet (god-file). Use:
  python -m hercules_cli.mesh
Doctor also prints the mesh.
"""

from __future__ import annotations

from typing import Callable


def build_mesh_parser(subparsers, *, cmd_mesh: Callable) -> None:
    parser = subparsers.add_parser(
        "mesh",
        help="Scan local agents/frameworks and list the Hercules mesh",
        description="Find .claude .opencode .openclaw .langchain pip/venv agents",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable")
    parser.set_defaults(func=cmd_mesh)
