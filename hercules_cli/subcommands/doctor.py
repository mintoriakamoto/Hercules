"""``hercules doctor`` subcommand parser.

Extracted verbatim from ``hercules_cli/main.py:main()`` (god-file Phase 2).
Handler injected to avoid importing ``main``.
"""

from __future__ import annotations

from typing import Callable


def build_doctor_parser(subparsers, *, cmd_doctor: Callable) -> None:
    """Attach the ``doctor`` subcommand to ``subparsers``."""
    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Check configuration, dependencies, and Hermes mesh",
        description="Diagnose issues with Cooklabs Hercules and list local agents",
    )
    doctor_parser.add_argument(
        "--fix", action="store_true", help="Attempt to fix issues automatically"
    )
    doctor_parser.add_argument(
        "--ack",
        metavar="ADVISORY_ID",
        default=None,
        help=(
            "Acknowledge a security advisory by ID and exit. After ack, the "
            "advisory will no longer trigger startup banners. Run `hercules "
            "doctor` first to see active advisories and their IDs."
        ),
    )

    def _doctor_with_hermes(args):
        try:
            from hercules_cli.hermes import format_report, scan

            print(format_report(scan()))
            print()
        except Exception as exc:  # mesh must never block doctor
            print(f"Hermes mesh skipped: {exc}")
        return cmd_doctor(args)

    doctor_parser.set_defaults(func=_doctor_with_hermes)
