"""Skill discovery and schema caching for startup performance.

Similar to tools/_builtin_module_cache.json, maintains a fingerprint-based
cache of discovered skills and their schemas to avoid rescanning on every
startup.

Potential savings: ~300-500ms on cold startup, <10ms on warm startup.
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_CACHE_FILE_NAME = ".skill_cache.json"


def _skills_fingerprint(skills_path: Path) -> str:
    """Generate fingerprint from skill directory state."""
    parts = []

    # Include all SKILL.md files
    for skill_md in sorted(skills_path.glob("**/SKILL.md")):
        try:
            mtime = skill_md.stat().st_mtime_ns
            parts.append(f"{skill_md.relative_to(skills_path)}:{mtime}")
        except (OSError, ValueError):
            pass

    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def load_skill_cache(skills_path: Path) -> Optional[Dict]:
    """Load cached skill metadata if fingerprint matches."""
    cache_file = skills_path / _CACHE_FILE_NAME
    try:
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        if data.get("fingerprint") == _skills_fingerprint(skills_path):
            return data.get("metadata")
    except Exception:
        pass
    return None


def save_skill_cache(skills_path: Path, metadata: Dict) -> None:
    """Save skill metadata with fingerprint."""
    cache_file = skills_path / _CACHE_FILE_NAME
    try:
        data = {
            "fingerprint": _skills_fingerprint(skills_path),
            "metadata": metadata,
        }
        cache_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    except Exception as exc:
        logger.debug("Could not write skill cache: %s", exc)


class SkillIndexCache:
    """In-memory cache for skill index operations."""

    def __init__(self):
        self._toolset_skills: Dict[str, List[str]] = {}
        self._skill_schemas: Dict[str, Dict] = {}
        self._dirty = False

    def get_skills_for_toolset(self, toolset: str) -> List[str]:
        """Get cached skills for a toolset."""
        return self._toolset_skills.get(toolset, [])

    def set_skills_for_toolset(self, toolset: str, skills: List[str]) -> None:
        """Cache skills for a toolset."""
        self._toolset_skills[toolset] = skills
        self._dirty = True

    def get_skill_schema(self, skill_name: str) -> Optional[Dict]:
        """Get cached skill schema."""
        return self._skill_schemas.get(skill_name)

    def set_skill_schema(self, skill_name: str, schema: Dict) -> None:
        """Cache skill schema."""
        self._skill_schemas[skill_name] = schema
        self._dirty = True

    def is_dirty(self) -> bool:
        """Check if cache has changed."""
        return self._dirty

    def reset_dirty(self) -> None:
        """Reset dirty flag after save."""
        self._dirty = False


# Global instance
_skill_index_cache = SkillIndexCache()


def get_global_skill_cache() -> SkillIndexCache:
    """Get the global skill index cache."""
    return _skill_index_cache
