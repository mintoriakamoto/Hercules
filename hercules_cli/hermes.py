"""Cooklabs mesh — Hermes-shaped, Hercules-owned.

Nous Hermes Agent layout we honor as a sidecar:
  ~/.hermes, HERMES_HOME, ~/.hermes/hermes-agent, hermes on PATH
We do not update from github.com/NousResearch/hermes-agent.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

HOME = Path.home()
OFFICIAL = "https://github.com/mintoriakamoto/Hercules"

MARKERS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("hermes-home", (".hermes",), "python -m hercules_cli.hermes_migrate"),
    ("hercules", (".hercules",), "this process"),
    ("claude", (".claude", ".config/claude"), "skills + CLAUDE.md + MCP"),
    ("opencode", (".opencode", ".config/opencode"), "MCP / CLI sidecar"),
    ("openclaw", (".openclaw", ".config/openclaw"), "hercules claw migrate"),
    ("langchain", (".langchain", ".config/langchain"), "import + venv site-packages"),
    ("cursor", (".cursor",), "rules / MCP"),
    ("continue", (".continue",), "config.yaml"),
    ("aider", (".aider",), "CLI sidecar"),
    ("goose", (".config/goose",), "CLI sidecar"),
    ("windsurf", (".codeium", ".windsurf"), "rules sidecar"),
)

HERMES_NESTED = (
    "config.yaml",
    ".env",
    "state.db",
    "skills",
    "hermes-agent",
    "venvs",
)

VENV_NAMES = (".venv", "venv", "env", ".env-venv")
PIP_HINTS = (
    "langchain",
    "langgraph",
    "openai",
    "anthropic",
    "claude-agent",
    "hercules",
    "hermes-agent",
)


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
    extra = os.environ.get("HERMES_HOME", "").strip()
    if extra:
        roots.append(Path(extra))
    for kind, rels, how in MARKERS:
        for root in roots:
            for rel in rels:
                path = (root / rel) if rel else root
                if not _exists(path):
                    continue
                key = f"{kind}:{path.resolve()}"
                if key in seen:
                    continue
                seen.add(key)
                found.append(Hit(kind, str(path), "dotdir", how))
                if kind == "hermes-home" and path.is_dir():
                    for nest in HERMES_NESTED:
                        child = path / nest
                        if _exists(child):
                            found.append(
                                Hit(
                                    f"hermes-{nest}",
                                    str(child),
                                    "dotdir",
                                    "migrate or leave as sidecar",
                                )
                            )
    return found


def _which_hits() -> list[Hit]:
    bins = {
        "hermes": "hermes",
        "hercules": "hercules",
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
    }
    how = {
        "hermes": "sidecar CLI — do not hermes update (that hits Nous)",
        "hercules": "this process; hercules update → mintoriakamoto/Hercules",
        "openclaw": "hercules claw migrate",
    }
    out: list[Hit] = []
    for kind, name in bins.items():
        path = shutil.which(name)
        if path:
            out.append(Hit(kind, path, "PATH", how.get(kind, "CLI sidecar")))
    return out


def _venv_hits(limit: int = 24) -> list[Hit]:
    out: list[Hit] = []
    search_roots = [
        Path.cwd(),
        HOME,
        HOME / ".hermes" / "venvs",
        HOME / ".hercules",
        HOME / "src",
        HOME / "dev",
        HOME / "code",
        HOME / "projects",
    ]
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


def _pip_show() -> list[str]:
    import subprocess

    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "freeze"],
            capture_output=True,
            text=True,
            timeout=8,
        )
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
    hits.extend(Hit("pip-pkg", n, "freeze", "import from active interpreter") for n in _pip_show())
    kinds = sorted({h.kind for h in hits})
    return {
        "home": str(HOME),
        "cwd": str(Path.cwd()),
        "official": OFFICIAL,
        "mesh": "hermes",
        "kinds": kinds,
        "hits": [asdict(h) for h in hits],
    }


def format_report(data: dict) -> str:
    lines = [
        "Hermes mesh (Cooklabs Hercules — Hermes-shaped, not Nous-owned)",
        f"official: {data['official']}",
        f"home: {data['home']}",
        f"kinds: {', '.join(data['kinds']) or '(none)'}",
        "",
    ]
    for h in data["hits"]:
        lines.append(f"  [{h['kind']:16}] {h['via']:8} {h['path']}")
        lines.append(f"                   {h['hermes']}")
    if not data["hits"]:
        lines.append("  (no local agent trees found under HOME / cwd / PATH)")
    lines.append("")
    lines.append("Together: Hercules owns the loop; sidecars stay CLI/MCP.")
    lines.append("Hermes Agent install → python -m hercules_cli.hermes_migrate")
    lines.append("OpenClaw → hercules claw migrate")
    lines.append("TENSELERATE → http://127.0.0.1:8080/v1")
    lines.append("update → hercules update (mintoriakamoto/Hercules only)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in {"migrate", "--migrate"}:
        from hercules_cli.hermes_migrate import main as migrate_main

        return migrate_main(argv[1:])
    data = scan()
    if argv and argv[0] in {"--json", "json"}:
        print(json.dumps(data, indent=2))
        return 0
    print(format_report(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
