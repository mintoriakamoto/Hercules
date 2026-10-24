#!/usr/bin/env python3
"""
Audit tool implementations.

Checks which tools from toolsets.py have implementations and which are missing.
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Set

# Add repo root to path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))

from toolsets import _HERCULES_CORE_TOOLS


def find_tool_implementations() -> Dict[str, List[str]]:
    """Find all tool implementations across the codebase."""
    tools_root = repo_root / "tools"
    implementations = {}

    # Search all Python files in tools/ directory
    for py_file in tools_root.glob("*.py"):
        if py_file.name.startswith("_"):
            continue

        content = py_file.read_text()

        # Find all @register_tool decorators with tool names
        pattern = r'@register_tool[(\s]*["\']([^"\']+)["\']'
        matches = re.findall(pattern, content)

        for tool_name in matches:
            if tool_name not in implementations:
                implementations[tool_name] = []
            implementations[tool_name].append(py_file.name)

    return implementations


def find_tool_definitions() -> Dict[str, str]:
    """Find all tool definitions (functions with tool names in docstrings)."""
    tools_root = repo_root / "tools"
    definitions = {}

    for py_file in tools_root.glob("*.py"):
        if py_file.name.startswith("_"):
            continue

        content = py_file.read_text()

        # Find all def lines followed by docstring mentioning the tool
        pattern = r'def\s+(\w+)\([^)]*\):[^:]*"""([^"]*(?:def\s+\w+|tool\s+[\w_]+)[^"]*)"""'

        # Simpler approach: look for def lines
        for line in content.split("\n"):
            # Check for @register_tool decorator
            if "@register_tool" in line:
                # Next few lines should have the function def
                pass

    return definitions


def main():
    """Audit tool implementations."""
    print("=" * 80)
    print("HERCULES TOOL AUDIT")
    print("=" * 80)

    # Get implemented tools
    implementations = find_tool_implementations()

    # Check each tool in the core list
    missing_tools = []
    implemented_tools = []

    for tool_name in sorted(_HERCULES_CORE_TOOLS):
        if tool_name in implementations:
            implemented_tools.append(tool_name)
            files = implementations[tool_name]
            print(f"✓ {tool_name:40} in {files}")
        else:
            missing_tools.append(tool_name)
            print(f"✗ {tool_name:40} MISSING")

    print()
    print("=" * 80)
    print(f"SUMMARY")
    print("=" * 80)
    print(f"Total tools: {len(_HERCULES_CORE_TOOLS)}")
    print(f"Implemented: {len(implemented_tools)}")
    print(f"Missing: {len(missing_tools)}")
    print(f"Coverage: {len(implemented_tools) / len(_HERCULES_CORE_TOOLS) * 100:.1f}%")

    if missing_tools:
        print()
        print("Missing tools by category:")

        # Categorize missing tools
        categories = {}
        for tool in missing_tools:
            prefix = tool.split("_")[0]
            if prefix not in categories:
                categories[prefix] = []
            categories[prefix].append(tool)

        for prefix in sorted(categories.keys()):
            tools = categories[prefix]
            print(f"  {prefix}: {len(tools)} tools")
            for tool in sorted(tools):
                print(f"    - {tool}")

    return 0 if not missing_tools else 1


if __name__ == "__main__":
    sys.exit(main())
