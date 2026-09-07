"""``hercules update`` subcommand parser.

Extracted verbatim from ``hercules_cli/main.py:main()`` (god-file Phase 2).
Handler injected to avoid importing ``main``.
"""

from __future__ import annotations

from typing import Callable


def build_update_parser(subparsers, *, cmd_update: Callable) -> None:
    """Attach the ``update`` subcommand to ``subparsers``."""
    update_parser = subparsers.add_parser(
        "update",
        help="Update Hercules Agent from github.com/mintoriakamoto/Hercules",
        description="Pull the latest changes from the Cooklabs GitHub repo and reinstall dependencies",
    )
    update_parser.add_argument(
        "--gateway",
        action="store_true",
        default=False,
        help="Gateway mode: use file-based IPC for prompts instead of stdin (used internally by /update)",
    )
    update_parser.add_argument(
        "--check",
        action="store_true",
        default=False,
        help="Check whether an update is available without installing anything",
    )
    update_parser.add_argument(
        "--no-backup",
        action="store_true",
        default=False,
        help="Skip the pre-update backup for this run (overrides updates.pre_update_backup)",
    )
    update_parser.add_argument(
        "--backup",
        action="store_true",
        default=False,
        help="Force a pre-update backup for this run (off by default; overrides updates.pre_update_backup=false)",
    )
    update_parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        default=False,
        help="Assume yes for interactive prompts (config migration, stash restore). API-key entry is skipped; run 'hercules config migrate' separately for those.",
    )
    update_parser.add_argument(
        "--branch",
        default=None,
        metavar="NAME",
        help=(
            "Update against this branch instead of the default (main). "
            "If the local checkout is on a different branch, hercules will "
            "switch to the requested branch first (auto-stashing any "
            "uncommitted changes)."
        ),
    )
    update_parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Windows: proceed with the update even when another hercules.exe is detected.",
    )
    update_parser.add_argument(
        "--force-venv",
        action="store_true",
        default=False,
        help="Windows: mutate the venv even while other processes are running from its interpreter.",
    )

    def _cooklabs_update(args):
        from hercules_cli.cooklabs_remote import ensure_cooklabs_origin

        ensure_cooklabs_origin()
        return cmd_update(args)

    update_parser.set_defaults(func=_cooklabs_update)
