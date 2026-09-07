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

    doctor_parser.set_defaults(func=cmd_doctor)
