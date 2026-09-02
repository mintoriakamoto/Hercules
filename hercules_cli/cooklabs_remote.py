"""Cooklabs update remote: `hercules update` / `/update` pull from this GitHub repo."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

COOKLABS_HTTPS = "https://github.com/mintoriakamoto/Hercules.git"
COOKLABS_SSH = "git@github.com:mintoriakamoto/Hercules.git"
COOKLABS_CANONICAL = "github.com/mintoriakamoto/hercules"

# hercules_cli/ is one level under the checkout root (same as main.PROJECT_ROOT).
CHECKOUT_ROOT = Path(__file__).resolve().parent.parent


def canonical_github_remote(url: Optional[str]) -> str:
    if not url:
        return ""
    value = url.strip()
    if value.startswith("git@github.com:"):
        value = "github.com/" + value[len("git@github.com:"):]
    elif value.startswith("ssh://git@github.com/"):
        value = "github.com/" + value[len("ssh://git@github.com/"):]
    elif "github.com" in value:
        value = value.replace("https://", "").replace("http://", "")
        value = value.split("@", 1)[-1]
    value = value.rstrip("/")
    if value.endswith(".git"):
        value = value[:-4]
    return value.lower()


def is_cooklabs_remote(url: Optional[str]) -> bool:
    return canonical_github_remote(url) == COOKLABS_CANONICAL


def is_ssh(url: Optional[str]) -> bool:
    value = (url or "").strip().lower()
    return value.startswith("git@") or value.startswith("ssh://")


def preferred_remote_url(current: Optional[str]) -> str:
    if current and is_ssh(current):
        return COOKLABS_SSH
    return COOKLABS_HTTPS


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def origin_url(cwd: Path) -> Optional[str]:
    result = _git(cwd, "remote", "get-url", "origin")
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def ensure_cooklabs_origin(cwd: Path | None = None) -> str:
    cwd = Path(cwd) if cwd is not None else CHECKOUT_ROOT
    current = origin_url(cwd)
    target = preferred_remote_url(current)
    if is_cooklabs_remote(current):
        return current or target
    if current is None:
        _git(cwd, "remote", "add", "origin", target)
    else:
        _git(cwd, "remote", "set-url", "origin", target)
    print(f"→ origin → {target}")
    return target
