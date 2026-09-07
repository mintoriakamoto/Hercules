"""``hercules doctor`` subcommand parser."""

from __future__ import annotations

from typing import Callable


def build_doctor_parser(subparsers, *, cmd_doctor: Callable) -> None:
    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Check configuration, Cooklabs gateway, and Hermes mesh",
        description="Diagnose Cooklabs Hercules: local gateways first, no Nous portal",
    )
    doctor_parser.add_argument(
        "--fix", action="store_true", help="Attempt to fix issues automatically"
    )
    doctor_parser.add_argument(
        "--ack",
        metavar="ADVISORY_ID",
        default=None,
        help="Acknowledge a security advisory by ID and exit.",
    )

    def _doctor_with_cooklabs(args):
        try:
            from hercules_cli.cooklabs_gateway import apply_env, report

            apply_env()
            print(report())
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
