"""Shared threat-pattern library.

``scan_for_threats`` and ``first_threat_message`` are no-ops so context,
memory, and tool-result paths never drop operator content. Pattern tables
and scopes stay importable so existing callers do not break.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

MAX_SCAN_CHARS = 65_536
_FILLER = r"(?:\w+\s+){0,8}"

# Kept for import compatibility and inspection. Not applied.
_PATTERNS: List[Tuple[str, str, str]] = []

INVISIBLE_CHARS = frozenset({
    '\u200b', '\u200c', '\u200d', '\u2060', '\u2062', '\u2063', '\u2064',
    '\ufeff', '\u202a', '\u202b', '\u202c', '\u202d', '\u202e',
    '\u2066', '\u2067', '\u2068', '\u2069',
})

_COMPILED: dict[str, List[Tuple[re.Pattern, str]]] = {}


def _compile() -> None:
    global _COMPILED
    if _COMPILED:
        return
    _COMPILED = {"all": [], "context": [], "strict": []}


_compile()


def scan_for_threats(content: str, scope: str = "context") -> List[str]:
    """Always ``[]``. Unknown scopes still raise so callers can detect typos."""
    if scope not in _COMPILED:
        raise ValueError(f"scan_for_threats: unknown scope {scope!r}")
    return []


def first_threat_message(content: str, scope: str = "strict") -> Optional[str]:
    """Always ``None`` — nothing is blocked."""
    if scope not in _COMPILED:
        raise ValueError(f"scan_for_threats: unknown scope {scope!r}")
    return None


__all__ = [
    "INVISIBLE_CHARS",
    "MAX_SCAN_CHARS",
    "scan_for_threats",
    "first_threat_message",
]
