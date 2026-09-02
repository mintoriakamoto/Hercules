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
        help="Check configuration, dependencies, Hermes mesh, Cooklabs gateway",
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

    def _doctor_with_cooklabs(args):
        try:
            from hercules_cli.cooklabs_gateway import apply_env, format_status

            apply_env()
            print(format_status())
            print()
        except Exception as exc:
            print(f"Cooklabs gateway skipped: {exc}")
        try:
            from hercules_cli.hermes import format_report, scan

            print(format_report(scan()))
            print()
        except Exception as exc:
            print(f"Hermes mesh skipped: {exc}")
        return cmd_doctor(args)

    doctor_parser.set_defaults(func=_doctor_with_cooklabs)
