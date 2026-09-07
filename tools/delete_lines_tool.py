#!/usr/bin/env python3
"""Delete Lines Tool - Remove specific lines from a file."""

from pathlib import Path
from typing import Dict, Any, List, Optional


def delete_lines_tool(
    filepath: str,
    start: Optional[int] = None,
    end: Optional[int] = None,
    line_numbers: Optional[List[int]] = None,
    pattern: Optional[str] = None,
    backup: bool = True,
) -> Dict[str, Any]:
    """
    Delete lines from a file by range, specific numbers, or pattern.

    Args:
        filepath: Path to file
        start: Start line number (1-indexed, inclusive)
        end: End line number (1-indexed, inclusive)
        line_numbers: Specific line numbers to delete
        pattern: Delete lines matching this substring
        backup: Create .bak backup before deleting (default: True)

    Returns:
        Dictionary with:
        - success: Whether deletion succeeded
        - lines_deleted: Number of lines removed
        - lines_remaining: Lines left in file
        - backup_file: Path to backup (if created)
        - filepath: Path to file

    Examples:
        # Delete lines 10-20
        delete_lines_tool("file.txt", start=10, end=20)

        # Delete specific lines
        delete_lines_tool("file.txt", line_numbers=[1, 5, 10])

        # Delete lines containing "TODO"
        delete_lines_tool("file.txt", pattern="TODO")

        # No backup
        delete_lines_tool("file.txt", start=1, end=5, backup=False)
    """
    path = Path(filepath).expanduser()

    if not path.exists():
        return {"error": f"File not found: {filepath}", "success": False}

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()

        total_lines = len(all_lines)
        lines_to_keep = []
        lines_deleted = 0

        if line_numbers:
            # Delete specific lines
            skip_set = set(line_numbers)
            for i, line in enumerate(all_lines, 1):
                if i not in skip_set:
                    lines_to_keep.append(line)
                else:
                    lines_deleted += 1

        elif pattern is not None:
            # Delete lines matching pattern
            for line in all_lines:
                if pattern in line:
                    lines_deleted += 1
                else:
                    lines_to_keep.append(line)

        else:
            # Delete range
            start_idx = (start or 1) - 1
            end_idx = (end or total_lines)

            if start_idx < 0:
                start_idx = 0
            if end_idx > total_lines:
                end_idx = total_lines

            for i, line in enumerate(all_lines):
                if i < start_idx or i >= end_idx:
                    lines_to_keep.append(line)
                else:
                    lines_deleted += 1

        # Create backup if requested
        backup_file = None
        if backup:
            backup_path = path.with_suffix(path.suffix + ".bak")
            with open(backup_path, "w", encoding="utf-8") as f:
                f.writelines(all_lines)
            backup_file = str(backup_path)

        # Write modified file
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(lines_to_keep)

        return {
            "success": True,
            "lines_deleted": lines_deleted,
            "lines_remaining": len(lines_to_keep),
            "backup_file": backup_file,
            "filepath": str(path),
        }

    except Exception as e:
        return {"error": f"Delete failed: {e}", "success": False}


def delete_empty_lines_tool(filepath: str, backup: bool = True) -> Dict[str, Any]:
    """
    Delete all empty lines from a file.

    Args:
        filepath: Path to file
        backup: Create .bak backup (default: True)

    Returns:
        Dictionary with deletion stats

    Examples:
        delete_empty_lines_tool("file.txt")
    """
    path = Path(filepath).expanduser()

    if not path.exists():
        return {"error": f"File not found: {filepath}", "success": False}

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()

        lines_to_keep = [line for line in all_lines if line.strip()]
        lines_deleted = len(all_lines) - len(lines_to_keep)

        backup_file = None
        if backup:
            backup_path = path.with_suffix(path.suffix + ".bak")
            with open(backup_path, "w", encoding="utf-8") as f:
                f.writelines(all_lines)
            backup_file = str(backup_path)

        with open(path, "w", encoding="utf-8") as f:
            f.writelines(lines_to_keep)

        return {
            "success": True,
            "lines_deleted": lines_deleted,
            "lines_remaining": len(lines_to_keep),
            "backup_file": backup_file,
            "filepath": str(path),
        }

    except Exception as e:
        return {"error": f"Delete empty lines failed: {e}", "success": False}
