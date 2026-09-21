"""Hercules + T3MP3ST + OBLITERATUS unified CLI bridge.

Does not import or vendor AGPL sources. Resolves the real binaries and
execs them so the War Room CLI and Hercules share one front door.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

T3MP3ST_REPO = "https://github.com/elder-plinius/T3MP3ST.git"
OBLITERATUS_REPO = "https://github.com/elder-plinius/OBLITERATUS.git"
DEFAULT_UI = "http://127.0.0.1:3333/ui/"

COMMAND_MAP = """
Hercules front door          → real binary
─────────────────────────────────────────────────────────────
hercules                     → hercules_cli.main (chat/gateway/doctor/…)
hercules warroom             → t3mp3st interactive (src/cli.ts)
hercules warroom server      → npm run server     (src/server.ts War Room)
hercules warroom status      → t3mp3st status
hercules warroom setup       → t3mp3st setup
hercules warroom models      → t3mp3st models
hercules warroom test        → t3mp3st test
hercules warroom open        → open War Room UI
hercules warroom doctor      → npm run doctor
hercules tempest …           → t3mp3st …          (alias)
hercules t3mp3st …           → t3mp3st …
hercules obliterate …        → obliteratus obliterate …
hercules obliteratus …       → obliteratus …
hercules abliterate …        → obliteratus …

Env:
  HERCULES_T3MP3ST_HOME     checkout path (default ~/.hercules/t3mp3st)
  HERCULES_OBLITERATUS_BIN  obliteratus executable
  T3MP3ST_PORT / T3MP3ST_HOST
"""


def _home() -> Path:
    raw = os.environ.get("HERCULES_HOME")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".hercules"


def t3_home() -> Path:
    raw = os.environ.get("HERCULES_T3MP3ST_HOME")
    if raw:
        return Path(raw).expanduser()
    return _home() / "t3mp3st"


def _run(cmd: list[str], *, cwd: Path | None = None) -> int:
    print("+", " ".join(cmd), file=sys.stderr)
    return subprocess.call(cmd, cwd=str(cwd) if cwd else None)


def ensure_t3mp3st() -> Path:
    dest = t3_home()
    marker = dest / "package.json"
    if marker.is_file():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"SUMMON T3MP3ST → {dest}", file=sys.stderr)
    rc = _run(["git", "clone", "--depth", "1", T3MP3ST_REPO, str(dest)])
    if rc != 0:
        raise SystemExit(f"git clone T3MP3ST failed ({rc})")
    _run(["npm", "install"], cwd=dest)
    return dest


def which_t3_bin() -> list[str] | None:
    for name in ("t3mp3st", "tempest"):
        found = shutil.which(name)
        if found:
            return [found]
    return None


def t3_cmd(args: list[str]) -> int:
    native = which_t3_bin()
    if native:
        return _run(native + args)
    dest = ensure_t3mp3st()
    npx = shutil.which("npx")
    if npx:
        return _run([npx, "--yes", "t3mp3st", *args], cwd=dest)
    node = shutil.which("node")
    cli_js = dest / "dist" / "cli.js"
    if node and cli_js.is_file():
        return _run([node, str(cli_js), *args], cwd=dest)
    raise SystemExit("t3mp3st not on PATH and npx/node unavailable. Install Node 22+.")


def warroom_server() -> int:
    dest = ensure_t3mp3st()
    npm = shutil.which("npm")
    if not npm:
        raise SystemExit("npm required to start War Room (src/server.ts)")
    print(f"War Room UI → {DEFAULT_UI}", file=sys.stderr)
    return _run([npm, "run", "server"], cwd=dest)


def warroom_doctor() -> int:
    dest = ensure_t3mp3st()
    npm = shutil.which("npm")
    if not npm:
        raise SystemExit("npm required for npm run doctor")
    return _run([npm, "run", "doctor"], cwd=dest)


def warroom_open() -> int:
    url = DEFAULT_UI
    opener = shutil.which("xdg-open") or shutil.which("open")
    if opener:
        return _run([opener, url])
    print(url)
    return 0


def which_obliteratus() -> list[str] | None:
    override = os.environ.get("HERCULES_OBLITERATUS_BIN")
    if override:
        return [override]
    found = shutil.which("obliteratus")
    if found:
        return [found]
    return None


def ensure_obliteratus() -> list[str]:
    native = which_obliteratus()
    if native:
        return native
    dest = _home() / "OBLITERATUS"
    if not (dest / "pyproject.toml").is_file():
        dest.parent.mkdir(parents=True, exist_ok=True)
        print(f"SUMMON OBLITERATUS → {dest}", file=sys.stderr)
        rc = _run(["git", "clone", "--depth", "1", OBLITERATUS_REPO, str(dest)])
        if rc != 0:
            raise SystemExit(f"git clone OBLITERATUS failed ({rc})")
    return [sys.executable, "-m", "obliteratus"]


def obliterate_cmd(args: list[str]) -> int:
    bin_ = ensure_obliteratus()
    env = os.environ.copy()
    dest = _home() / "OBLITERATUS"
    if dest.is_dir():
        env["PYTHONPATH"] = str(dest) + os.pathsep + env.get("PYTHONPATH", "")
    print("+", " ".join(bin_ + args), file=sys.stderr)
    return subprocess.call(bin_ + args, env=env, cwd=str(dest) if dest.is_dir() else None)


def _help() -> int:
    print(COMMAND_MAP.strip())
    return 0


# Verbs this bridge owns. Everything else — including no args, -h/--help, and
# plugin-registered subcommands — belongs to hercules_cli.main. These must be
# intercepted before main.py's argparse: none of them are in its
# _BUILTIN_SUBCOMMANDS set, so reaching it would trigger a full plugin
# discovery pass and then still fail to parse.
_WARROOM_VERBS = frozenset(
    {"warroom", "tempest", "t3mp3st", "obliterate", "obliteratus", "abliterate"}
)


def _delegate(args: list[str]) -> int:
    """Hand a non-warroom invocation to the real Hercules CLI."""
    # Lazy: hercules_cli.main is 14.7k lines and imports this package's
    # siblings, so a module-level import here would cycle.
    from hercules_cli.main import main as _hercules_main

    argv_backup = sys.argv
    sys.argv = [argv_backup[0], *args]
    try:
        return int(_hercules_main() or 0)
    except SystemExit as exc:
        if exc.code is None:
            return 0
        return exc.code if isinstance(exc.code, int) else 1
    finally:
        sys.argv = argv_backup


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] not in _WARROOM_VERBS:
        return _delegate(args)

    verb = args[0]
    rest = args[1:]

    if verb == "warroom":
        if not rest or rest[0] in {"interactive", "cli"}:
            return t3_cmd([])
        sub = rest[0]
        if sub in {"server", "ui", "start"}:
            return warroom_server()
        if sub in {"open", "browse"}:
            return warroom_open()
        if sub == "doctor":
            return warroom_doctor()
        if sub in {"map", "help"}:
            return _help()
        if sub in {"status", "setup", "models", "test"}:
            return t3_cmd([sub, *rest[1:]])
        return t3_cmd(rest)

    if verb in {"tempest", "t3mp3st"}:
        if rest and rest[0] in {"server", "ui", "start"}:
            return warroom_server()
        return t3_cmd(rest)

    if verb in {"obliterate", "obliteratus", "abliterate"}:
        if verb == "obliteratus":
            return obliterate_cmd(rest)
        return obliterate_cmd(["obliterate", *rest] if rest[:1] != ["obliterate"] else rest)

    return _help()


if __name__ == "__main__":
    raise SystemExit(main())
