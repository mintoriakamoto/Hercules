"""Cooklabs update remote: `hercules update` / `/update` pull from this GitHub repo.

If origin still points at NousResearch (or anything else), retarget it to
https://github.com/mintoriakamoto/Hercules.git so fetch/pull stay first-party.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

COOKLABS_HTTPS = "https://github.com/mintoriakamoto/Hercules.git"
COOKLABS_SSH = "git@github.com:mintoriakamoto/Hercules.git"
COOKLABS_CANONICAL = "github.com/mintoriakamoto/hercules"


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


def preferred_remote_url(current: Optional[str]) -> str:
    if current and is_ssh(current):
        return COOKLABS_SSH
    return COOKLABS_HTTPS


def is_ssh(url: Optional[str]) -> bool:
    value = (url or "").strip().lower()
    return value.startswith("git@") or value.startswith("ssh://")


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def origin_url(cwd: Path) -> Optional[str]:
    result = _git(cwd, "remote", "get-url", "origin")
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def ensure_cooklabs_origin(cwd: Path | None = None) -> str:
    """Make origin the Cooklabs Hercules repo. Returns the URL in use."""
    if cwd is None:
        from hercules_constants import PROJECT_ROOT

        cwd = PROJECT_ROOT
    cwd = Path(cwd)
    current = origin_url(cwd)
    target = preferred_remote_url(current)
    if is_cooklabs_remote(current):
        return current or target
    if current is None:
        added = _git(cwd, "remote", "add", "origin", target)
        if added.returncode != 0:
            _git(cwd, "remote", "set-url", "origin", target)
        print(f"→ origin set to {target}")
        return target
    _git(cwd, "remote", "rename", "origin", "upstream-old")
    set_url = _git(cwd, "remote", "set-url", "origin", target)
    if set_url.returncode != 0:
        _git(cwd, "remote", "add", "origin", target)
        _git(cwd, "remote", "set-url", "origin", target)
    print(f"→ origin was {current}")
    print(f"→ origin now {target} (Cooklabs)")
    return target
