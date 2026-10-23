#!/usr/bin/env python3
"""Regenerate startup caches: tool-module discovery and bundled skill index.

Run this after adding/removing tool modules or SKILL.md files so the caches
stay in sync with the source tree.  CI runs this automatically; developers
can run it manually after local changes.

    python scripts/regen_caches.py

Outputs:
  tools/_builtin_module_cache.json   — list of tool modules that register tools
  skills/index-cache/bundled_skills.json — structured JSON index of bundled skills
"""

import ast
import hashlib
import json
import os
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = REPO_ROOT / "tools"
SKILLS_DIR = REPO_ROOT / "skills"
MODULE_CACHE = TOOLS_DIR / "_builtin_module_cache.json"
SKILL_INDEX = SKILLS_DIR / "index-cache" / "bundled_skills.json"
EXCLUDED_TOOLS = {"__init__.py", "registry.py", "mcp_tool.py"}
SKILL_SUPPORT_DIRS = {"references", "examples", "templates", "docs", "assets", ".curator_backups"}


# ---------------------------------------------------------------------------
# Tool module cache
# ---------------------------------------------------------------------------

def _is_registry_register_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
        return False
    func = node.value.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "register"
        and isinstance(func.value, ast.Name)
        and func.value.id == "registry"
    )


def _module_registers_tools(path: Path) -> bool:
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return False
    if "registry.register(" not in source:
        return False
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return False

    def _has_register(node: ast.AST) -> bool:
        if _is_registry_register_call(node):
            return True
        if isinstance(node, ast.For):
            return any(_is_registry_register_call(s) for s in node.body)
        return False

    return any(_has_register(stmt) for stmt in tree.body)


def regen_tool_cache() -> int:
    files = sorted(TOOLS_DIR.glob("*.py"))
    fingerprint_input = "|".join(f"{p.name}:{p.stat().st_mtime_ns}" for p in files)
    fingerprint = hashlib.sha256(fingerprint_input.encode()).hexdigest()[:16]

    modules = [
        p.stem
        for p in sorted(TOOLS_DIR.glob("*.py"))
        if p.name not in EXCLUDED_TOOLS and _module_registers_tools(p)
    ]
    MODULE_CACHE.write_text(
        json.dumps({"fingerprint": fingerprint, "modules": modules}, indent=2) + "\n",
        encoding="utf-8",
    )
    return len(modules)


# ---------------------------------------------------------------------------
# Bundled skill index
# ---------------------------------------------------------------------------

def _parse_frontmatter(src: str) -> dict:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", src, re.DOTALL)
    if not m:
        return {}
    raw = m.group(1)
    if yaml is not None:
        try:
            result = yaml.safe_load(raw)
            return result if isinstance(result, dict) else {}
        except Exception:
            pass
    # Minimal fallback: extract name and description lines without PyYAML
    result: dict = {}
    for line in raw.splitlines():
        for key in ("name", "description", "version", "author"):
            prefix = f"{key}:"
            if line.startswith(prefix):
                result[key] = line[len(prefix):].strip().strip('"').strip("'")
    return result


def regen_skill_index() -> int:
    skills = []
    for p in sorted(SKILLS_DIR.rglob("SKILL.md")):
        if any(part in SKILL_SUPPORT_DIRS for part in p.parts):
            continue
        try:
            src = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        fm = _parse_frontmatter(src)
        herc_meta = (fm.get("metadata") or {}).get("hercules", {}) if isinstance(fm.get("metadata"), dict) else {}
        skills.append({
            "name": fm.get("name") or p.parent.name,
            "description": fm.get("description", ""),
            "version": fm.get("version", ""),
            "author": fm.get("author", ""),
            "platforms": fm.get("platforms", []),
            "tags": herc_meta.get("tags", fm.get("tags", [])),
            "category": herc_meta.get("category", ""),
            "path": str(p.relative_to(SKILLS_DIR)),
            "prerequisites": fm.get("prerequisites", {}),
            "required_credential_files": [
                c.get("path", "") for c in (fm.get("required_credential_files") or [])
                if isinstance(c, dict)
            ],
        })
    SKILL_INDEX.parent.mkdir(parents=True, exist_ok=True)
    SKILL_INDEX.write_text(
        json.dumps({"generated_at": "2026-10-21", "count": len(skills), "skills": skills}, indent=2) + "\n",
        encoding="utf-8",
    )
    return len(skills)


if __name__ == "__main__":
    n_tools = regen_tool_cache()
    print(f"tools/_builtin_module_cache.json: {n_tools} modules")

    n_skills = regen_skill_index()
    print(f"skills/index-cache/bundled_skills.json: {n_skills} skills")
