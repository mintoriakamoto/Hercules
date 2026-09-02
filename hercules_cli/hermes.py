"""Hermes — local agent/framework mesh under Cooklabs Hercules.

Scans the home machine for Claude, OpenCode, OpenClaw, LangChain, pip/venv
installs and other agent trees. Does not walk the entire disk.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

HOME = Path.home()

# Name, relative markers under HOME (and cwd), how Hercules talks to it.
MARKERS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("claude", (".claude", ".config/claude"), "skills + CLAUDE.md + MCP"),
    ("opencode", (".opencode", ".config/opencode"), "MCP / CLI sidecar"),
    ("openclaw", (".openclaw", ".config/openclaw"), "hercules claw migrate"),
    ("langchain", (".langchain", ".config/langchain"), "import + venv site-packages"),
    ("hercules", (".hercules",), "this process"),
    ("cursor", (".cursor",), "rules / MCP"),
    ("continue", (".continue",), "config.yaml"),
    ("aider", (".aider",), "CLI sidecar"),
    ("goose", (".config/goose",), "CLI sidecar"),
    ("windsurf", (".codeium", ".windsurf"), "rules sidecar"),
)

VENV_NAMES = (".venv", "venv", "env", ".env-venv")
PIP_HINTS = ("langchain", "langgraph", "openai", "anthropic", "claude-agent", "hercules")


@dataclass
class Hit:
    kind: str
    path: str
    via: str
    hermes: str


def _exists(p: Path) -> bool:
    try:
        return p.exists()
    except OSError:
        return False


def _home_hits() -> list[Hit]:
    found: list[Hit] = []
    seen: set[str] = set()
    roots = [HOME, Path.cwd()]
    for kind, rels, how in MARKERS:
        for root in roots:
            for rel in rels:
                path = root / rel
                if not _exists(path):
                    continue
                key = f"{kind}:{path.resolve()}"
                if key in seen:
                    continue
                seen.add(key)
                found.append(Hit(kind, str(path), "dotdir", how))
    return found


def _which_hits() -> list[Hit]:
    bins = {
        "claude": "claude",
        "opencode": "opencode",
        "openclaw": "openclaw",
        "langchain": "langchain",
        "aider": "aider",
        "goose": "goose",
        "cursor": "cursor",
        "pip": "pip",
        "pip3": "pip3",
        "uv": "uv",
        "poetry": "poetry",
        "hercules": "hercules",
    }
    how = {
        "claude": "CLI sidecar",
        "opencode": "CLI sidecar",
        "openclaw": "hercules claw migrate",
        "langchain": "venv import",
        "pip": "package index",
        "pip3": "package index",
        "uv": "package index",
        "poetry": "package index",
        "hercules": "this process",
    }
    out: list[Hit] = []
    for kind, name in bins.items():
        path = shutil.which(name)
        if path:
            out.append(Hit(kind, path, "PATH", how.get(kind, "CLI sidecar")))
    return out


def _venv_hits(limit: int = 24) -> list[Hit]:
    out: list[Hit] = []
    search_roots = [Path.cwd(), HOME, HOME / "src", HOME / "dev", HOME / "code", HOME / "projects"]
    seen: set[str] = set()
    for root in search_roots:
        if not _exists(root) or not root.is_dir():
            continue
        try:
            children = list(root.iterdir())
        except OSError:
            continue
        candidates = [root] + [p for p in children if p.is_dir()][:80]
        for folder in candidates:
            for name in VENV_NAMES:
                venv = folder / name
                py = venv / "bin" / "python"
                if not py.exists():
                    py = venv / "Scripts" / "python.exe"
                if not py.exists():
                    continue
                key = str(venv.resolve()) if venv.exists() else str(venv)
                if key in seen:
                    continue
                seen.add(key)
                out.append(Hit("venv", key, "fs", "run tools inside interpreter"))
                if len(out) >= limit:
                    return out
    return out


def _pip_show(venv_python: Path | None = None) -> list[str]:
    import subprocess

    cmd = [str(venv_python)] if venv_python else [sys.executable]
    cmd += ["-m", "pip", "freeze"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0:
        return []
    names = []
    for line in proc.stdout.splitlines():
        pkg = line.split("==", 1)[0].split(" @ ", 1)[0].strip().lower()
        if any(h in pkg for h in PIP_HINTS):
            names.append(line.strip())
    return names


def scan() -> dict:
    hits = _home_hits() + _which_hits() + _venv_hits()
    pip_hits = [Hit("pip-pkg", n, "freeze", "import from active interpreter") for n in _pip_show()]
    hits.extend(pip_hits)
    kinds = sorted({h.kind for h in hits})
    return {
        "home": str(HOME),
        "cwd": str(Path.cwd()),
        "official": "https://github.com/mintoriakamoto/Hercules",
        "mesh": "hermes",
        "kinds": kinds,
        "hits": [asdict(h) for h in hits],
    }


def format_report(data: dict) -> str:
    lines = [
        "Hermes mesh (Cooklabs Hercules)",
        f"official: {data['official']}",
        f"home: {data['home']}",
        f"kinds: {', '.join(data['kinds']) or '(none)'}",
        "",
    ]
    for h in data["hits"]:
        lines.append(f"  [{h['kind']:12}] {h['via']:8} {h['path']}")
        lines.append(f"               hermes: {h['hermes']}")
    if not data["hits"]:
        lines.append("  (no local agent trees found under HOME / cwd / PATH)")
    lines.append("")
    lines.append("Together: Hercules owns the loop; sidecars stay CLI/MCP.")
    lines.append("OpenClaw → hercules claw migrate")
    lines.append("TENSELERATE → http://127.0.0.1:8080/v1")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    data = scan()
    if argv and argv[0] in {"--json", "json"}:
        print(json.dumps(data, indent=2))
        return 0
    print(format_report(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
