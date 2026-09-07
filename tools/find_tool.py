#!/usr/bin/env python3
"""
Find Tool - Search for files by name, pattern, or properties.

Simple file discovery tool that works like Unix find but returns structured results.
"""

import os
import re
from pathlib import Path
from typing import Optional, List, Dict, Any
import fnmatch


def find_tool(
    path: str = ".",
    pattern: Optional[str] = None,
    file_type: Optional[str] = None,
    max_results: int = 100,
    ignore_hidden: bool = True,
) -> Dict[str, Any]:
    """
    Find files by name or pattern.

    Args:
        path: Directory to search (default: current directory)
        pattern: Filename pattern (e.g., "*.py", "test_*")
        file_type: Filter by type - "file", "dir", or None for both
        max_results: Maximum number of results (default: 100)
        ignore_hidden: Skip hidden files/dirs starting with . (default: True)

    Returns:
        Dictionary with:
        - found: List of matched file paths
        - count: Number of results
        - truncated: Whether results were truncated
        - search_path: Directory searched

    Examples:
        # Find all Python files
        find_tool(".", pattern="*.py")

        # Find all directories named 'tests'
        find_tool(".", pattern="tests", file_type="dir")

        # Find files matching regex-like pattern
        find_tool("./src", pattern="test_*.py")
    """
    base_path = Path(path).expanduser()

    if not base_path.exists():
        return {
            "error": f"Path not found: {path}",
            "found": [],
            "count": 0,
            "truncated": False,
        }

    if not base_path.is_dir():
        return {
            "error": f"Not a directory: {path}",
            "found": [],
            "count": 0,
            "truncated": False,
        }

    results = []

    try:
        for root, dirs, files in os.walk(base_path):
            # Filter hidden directories to speed up traversal
            if ignore_hidden:
                dirs[:] = [d for d in dirs if not d.startswith(".")]

            # Search files
            if file_type in (None, "file"):
                for name in files:
                    if ignore_hidden and name.startswith("."):
                        continue

                    if pattern is None or fnmatch.fnmatch(name, pattern):
                        full_path = os.path.join(root, name)
                        results.append(full_path)

                        if len(results) >= max_results:
                            return {
                                "found": results[:max_results],
                                "count": max_results,
                                "truncated": True,
                                "search_path": str(base_path),
                                "note": f"Limited to {max_results} results",
                            }

            # Search directories
            if file_type in (None, "dir"):
                for name in dirs:
                    if ignore_hidden and name.startswith("."):
                        continue

                    if pattern is None or fnmatch.fnmatch(name, pattern):
                        full_path = os.path.join(root, name)
                        results.append(full_path)

                        if len(results) >= max_results:
                            return {
                                "found": results[:max_results],
                                "count": max_results,
                                "truncated": True,
                                "search_path": str(base_path),
                                "note": f"Limited to {max_results} results",
                            }

    except PermissionError as e:
        return {
            "error": f"Permission denied: {e}",
            "found": results,
            "count": len(results),
            "truncated": False,
            "search_path": str(base_path),
        }

    return {
        "found": results,
        "count": len(results),
        "truncated": False,
        "search_path": str(base_path),
    }
