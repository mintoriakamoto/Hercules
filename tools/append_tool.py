#!/usr/bin/env python3
"""Append Tool - Add lines to the end of a file."""

from pathlib import Path
from typing import Dict, Any, List


def append_tool(filepath: str, content: str, create_if_missing: bool = True) -> Dict[str, Any]:
    """
    Append content to the end of a file.

    Args:
        filepath: Path to file
        content: Content to append (can be multi-line)
        create_if_missing: Create file if it doesn't exist (default: True)

    Returns:
        Dictionary with:
        - success: Whether operation succeeded
        - lines_added: Number of lines added
        - file_size_before: Size before append
        - file_size_after: Size after append
        - filepath: Path to file

    Examples:
        append_tool("log.txt", "New entry\\n")
        append_tool("notes.md", "\\n## New Section\\n")
    """
    path = Path(filepath).expanduser()

    try:
        # Check if file exists
        if path.exists():
            size_before = path.stat().st_size
        else:
            if not create_if_missing:
                return {
                    "error": f"File not found and create_if_missing=False: {filepath}",
                    "success": False,
                }
            size_before = 0

        # Count lines to be added
        lines_added = content.count("\n")
        if content and not content.endswith("\n"):
            lines_added += 1

        # Append content
        with open(path, "a", encoding="utf-8") as f:
            f.write(content)

        size_after = path.stat().st_size

        return {
            "success": True,
            "lines_added": lines_added,
            "file_size_before": size_before,
            "file_size_after": size_after,
            "filepath": str(path),
        }

    except Exception as e:
        return {"error": f"Append failed: {e}", "success": False}
