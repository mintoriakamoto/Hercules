#!/usr/bin/env python3
"""
Compare Files Tool - Simple file comparison with unified diff output.

Compare two files and show differences in a human-readable format.
"""

import difflib
from pathlib import Path
from typing import Dict, Any, List


def compare_files_tool(
    file1: str,
    file2: str,
    context_lines: int = 3,
    ignore_whitespace: bool = False,
) -> Dict[str, Any]:
    """
    Compare two files and show differences.

    Args:
        file1: Path to first file
        file2: Path to second file
        context_lines: Lines of context around differences (default: 3)
        ignore_whitespace: Ignore whitespace-only changes (default: False)

    Returns:
        Dictionary with:
        - identical: Boolean whether files are identical
        - diff_lines: List of diff lines (unified format)
        - additions: Number of added lines
        - deletions: Number of deleted lines
        - changes: Number of changed lines
        - summary: Human-readable summary

    Examples:
        # Compare two Python files
        compare_files_tool("old.py", "new.py")

        # Show more context
        compare_files_tool("config.yaml", "config.new.yaml", context_lines=5)
    """
    path1 = Path(file1).expanduser()
    path2 = Path(file2).expanduser()

    # Validate files exist
    if not path1.exists():
        return {"error": f"File not found: {file1}", "identical": None}

    if not path2.exists():
        return {"error": f"File not found: {file2}", "identical": None}

    try:
        with open(path1, "r", encoding="utf-8", errors="replace") as f:
            lines1 = f.readlines()
    except Exception as e:
        return {"error": f"Cannot read {file1}: {e}", "identical": None}

    try:
        with open(path2, "r", encoding="utf-8", errors="replace") as f:
            lines2 = f.readlines()
    except Exception as e:
        return {"error": f"Cannot read {file2}: {e}", "identical": None}

    # Check if files are identical
    if lines1 == lines2:
        return {
            "identical": True,
            "diff_lines": [],
            "additions": 0,
            "deletions": 0,
            "changes": 0,
            "summary": "Files are identical",
        }

    # Generate unified diff
    diff_gen = difflib.unified_diff(
        lines1,
        lines2,
        fromfile=str(path1),
        tofile=str(path2),
        n=context_lines,
        lineterm="",
    )

    diff_lines = list(diff_gen)

    # Count changes
    additions = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
    deletions = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))
    changes = max(additions, deletions)

    summary = f"Differences: {additions} additions, {deletions} deletions, {changes} changed lines"

    return {
        "identical": False,
        "diff_lines": diff_lines,
        "additions": additions,
        "deletions": deletions,
        "changes": changes,
        "summary": summary,
        "file1": str(path1),
        "file2": str(path2),
    }


def count_file_lines_tool(
    filepath: str,
    count_empty: bool = True,
    count_comments: bool = True,
) -> Dict[str, Any]:
    """
    Count lines in a file with breakdown.

    Args:
        filepath: Path to file
        count_empty: Include empty lines (default: True)
        count_comments: Count comment lines separately (default: True)

    Returns:
        Dictionary with:
        - total: Total number of lines
        - empty: Number of empty lines
        - comments: Number of comment lines (if count_comments=True)
        - code: Non-empty, non-comment lines
        - file: Path analyzed

    Examples:
        # Count lines in a Python file
        count_file_lines_tool("main.py")
    """
    path = Path(filepath).expanduser()

    if not path.exists():
        return {"error": f"File not found: {filepath}"}

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception as e:
        return {"error": f"Cannot read {filepath}: {e}"}

    total = len(lines)
    empty = sum(1 for line in lines if line.strip() == "")

    # Simple comment detection (works for #, //, --)
    comments = 0
    if count_comments:
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("--"):
                comments += 1

    code = total - empty - comments

    return {
        "total": total,
        "empty": empty,
        "comments": comments if count_comments else 0,
        "code": code,
        "file": str(path),
    }
