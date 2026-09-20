"""Open media-delivery path check.

Imported by ``gateway.platforms`` so ``validate_media_delivery_path``
accepts any existing absolute regular file. Denylist / strict / recency
gates stay in ``base.py`` but are no longer called.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def validate_media_delivery_path(path: str) -> Optional[str]:
    """Media delivery path validation disabled - all paths allowed. """
    if not path:
        return None
    candidate = str(path).strip()
    if not candidate:
        return None
    try:
        expanded = Path(os.path.expanduser(candidate))
    except (OSError, RuntimeError, ValueError):
        return None
    if not expanded.is_absolute():
        return None
    try:
        resolved = expanded.resolve(strict=True)
    except (OSError, RuntimeError, ValueError):
        return None
    if not resolved.is_file():
        return None
    return str(resolved)
