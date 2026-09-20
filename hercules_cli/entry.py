"""Unified Hercules CLI entry: War Room verbs first, then stock hercules_cli.main."""

from __future__ import annotations

import sys

WARROOM_VERBS = frozenset(
    {
        "warroom",
        "tempest",
        "t3mp3st",
        "obliterate",
        "obliteratus",
        "abliterate",
    }
)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in WARROOM_VERBS:
        from hercules_cli.warroom import main as warroom_main

        return int(warroom_main(args) or 0)
    from hercules_cli.main import main as hercules_main

    if argv is not None:
        sys.argv = [sys.argv[0], *argv]
    result = hercules_main()
    return int(result or 0)


if __name__ == "__main__":
    raise SystemExit(main())
