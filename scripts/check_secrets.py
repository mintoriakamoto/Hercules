#!/usr/bin/env python3
"""Pre-commit secret guard.

Blocks a commit when a staged file is a real env file (``.env``, ``.env.*``
other than ``.env.example``) or when staged content contains something shaped
like a live provider key or a private key.

Findings are reported by file, line and rule only. The matched text is never
printed, so the hook output itself cannot leak a key into a terminal log or CI.

Usage (pre-commit passes the staged file names):
    python scripts/check_secrets.py FILE [FILE ...]

A line can opt out with a trailing ``# secret-scan: allow`` comment, for test
fixtures that need a key-shaped string.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ALLOW_MARKER = "secret-scan: allow"

# Env files that must never be committed. ``.env.example`` holds placeholders.
_ENV_FILE = re.compile(r"(^|/)\.env(\..+)?$")
_ENV_ALLOWED = {".env.example"}

RULES: dict[str, re.Pattern[str]] = {
    "OpenRouter key": re.compile(r"sk-or-v1-[0-9a-f]{40,}"),
    "Anthropic key": re.compile(r"sk-ant-(?:api|admin)\d\d-[A-Za-z0-9_-]{60,}"),
    "OpenAI key": re.compile(r"sk-(?:proj|svcacct)-[A-Za-z0-9_-]{40,}"),
    "Groq key": re.compile(r"gsk_[A-Za-z0-9]{40,}"),
    "xAI key": re.compile(r"xai-[A-Za-z0-9]{60,}"),
    "Google API key": re.compile(r"AIza[0-9A-Za-z_-]{35}"),
    "Hugging Face token": re.compile(r"\bhf_[A-Za-z0-9]{34,}"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{60,}"),
    "Slack token": re.compile(r"xox[baprs]-\d{9,}-[0-9A-Za-z-]{20,}"),
    "Telegram bot token": re.compile(r"\b\d{8,10}:AA[A-Za-z0-9_-]{33}\b"),
    "AWS access key": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "NVIDIA key": re.compile(r"nvapi-[A-Za-z0-9_-]{60,}"),
    "Stripe live key": re.compile(r"\b[sr]k_live_[0-9a-zA-Z]{24,}"),
    "Private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----\s*$"),
}


# Obvious placeholders (AWS's documented EXAMPLE keys, runs of one character,
# "fake"/"test" markers) are fixtures, not secrets.
_PLACEHOLDER = re.compile(r"(?i)example|fake|test|dummy|xxxx|0000|1234|abcd|(.)\1{5,}")


def scan_text(text: str) -> list[tuple[int, str]]:
    """Return (line_number, rule) for each finding. Never returns matched text."""
    findings: list[tuple[int, str]] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if ALLOW_MARKER in line:
            continue
        for rule, pattern in RULES.items():
            match = pattern.search(line)
            if match and not _PLACEHOLDER.search(match.group(0)):
                findings.append((lineno, rule))
    return findings


def is_forbidden_env_file(path: str) -> bool:
    name = Path(path).name
    return bool(_ENV_FILE.search(path.replace("\\", "/"))) and name not in _ENV_ALLOWED


def main(argv: list[str]) -> int:
    problems: list[str] = []
    for path in argv:
        if is_forbidden_env_file(path):
            problems.append(f"{path}: env files must not be committed (use .env.example)")
            continue
        p = Path(path)
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binary or unreadable: out of scope for this guard
        for lineno, rule in scan_text(text):
            problems.append(f"{path}:{lineno}: looks like a {rule}")
    if problems:
        print("Secret guard blocked this commit:")
        for line in problems:
            print(f"  {line}")
        print(
            "Move the value to your local ~/.hercules/.env, or mark a test "
            f"fixture line with '# {ALLOW_MARKER}'."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
