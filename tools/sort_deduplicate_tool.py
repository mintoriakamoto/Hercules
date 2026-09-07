#!/usr/bin/env python3
"""Sort and Deduplicate Tools - Organize and clean file contents."""

from pathlib import Path
from typing import Dict, Any


def sort_lines_tool(
    filepath: str,
    reverse: bool = False,
    ignore_case: bool = False,
    backup: bool = True,
) -> Dict[str, Any]:
    """
    Sort lines in a file alphabetically.

    Args:
        filepath: Path to file
        reverse: Sort in reverse order (default: False)
        ignore_case: Case-insensitive sort (default: False)
        backup: Create .bak backup (default: True)

    Returns:
        Dictionary with:
        - success: Whether sort succeeded
        - lines_sorted: Number of lines sorted
        - backup_file: Path to backup (if created)
        - filepath: Path to file

    Examples:
        sort_lines_tool("words.txt")  # A-Z
        sort_lines_tool("words.txt", reverse=True)  # Z-A
        sort_lines_tool("urls.txt", ignore_case=True)
    """
    path = Path(filepath).expanduser()

    if not path.exists():
        return {"error": f"File not found: {filepath}", "success": False}

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()

        # Preserve line endings
        lines_with_endings = [(line.rstrip("\n"), line.endswith("\n")) for line in all_lines]
        lines_content = [l[0] for l in lines_with_endings]

        # Sort
        sorted_lines = sorted(lines_content, key=lambda x: x.lower() if ignore_case else x, reverse=reverse)

        # Restore line endings
        sorted_output = [line + ("\n" if endings else "") for line, (_, endings) in zip(sorted_lines, lines_with_endings)]

        # Create backup if requested
        backup_file = None
        if backup:
            backup_path = path.with_suffix(path.suffix + ".bak")
            with open(backup_path, "w", encoding="utf-8") as f:
                f.writelines(all_lines)
            backup_file = str(backup_path)

        # Write sorted file
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(sorted_output)

        return {
            "success": True,
            "lines_sorted": len(all_lines),
            "backup_file": backup_file,
            "filepath": str(path),
        }

    except Exception as e:
        return {"error": f"Sort failed: {e}", "success": False}


def deduplicate_lines_tool(
    filepath: str,
    preserve_order: bool = True,
    backup: bool = True,
) -> Dict[str, Any]:
    """
    Remove duplicate lines from a file.

    Args:
        filepath: Path to file
        preserve_order: Keep original line order (default: True)
        backup: Create .bak backup (default: True)

    Returns:
        Dictionary with:
        - success: Whether deduplication succeeded
        - lines_before: Number of lines before
        - lines_after: Number of lines after (duplicates removed)
        - duplicates_removed: Count of removed duplicates
        - backup_file: Path to backup (if created)
        - filepath: Path to file

    Examples:
        deduplicate_lines_tool("list.txt")
        deduplicate_lines_tool("ids.txt", preserve_order=False)  # Faster
    """
    path = Path(filepath).expanduser()

    if not path.exists():
        return {"error": f"File not found: {filepath}", "success": False}

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()

        lines_before = len(all_lines)

        if preserve_order:
            # Keep order: use dict (Python 3.7+ dicts maintain insertion order)
            seen = {}
            unique_lines = []
            for line in all_lines:
                content = line.rstrip("\n")
                if content not in seen:
                    seen[content] = True
                    unique_lines.append(line)
        else:
            # Don't preserve order: simpler/faster
            unique_lines = list(dict.fromkeys(all_lines))

        duplicates_removed = lines_before - len(unique_lines)

        # Create backup if requested
        backup_file = None
        if backup:
            backup_path = path.with_suffix(path.suffix + ".bak")
            with open(backup_path, "w", encoding="utf-8") as f:
                f.writelines(all_lines)
            backup_file = str(backup_path)

        # Write deduplicated file
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(unique_lines)

        return {
            "success": True,
            "lines_before": lines_before,
            "lines_after": len(unique_lines),
            "duplicates_removed": duplicates_removed,
            "backup_file": backup_file,
            "filepath": str(path),
        }

    except Exception as e:
        return {"error": f"Deduplicate failed: {e}", "success": False}
