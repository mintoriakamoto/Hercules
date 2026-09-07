#!/usr/bin/env python3
"""Extract Lines Tool - Get specific lines or ranges from a file."""

from pathlib import Path
from typing import Dict, Any, Optional, List


def extract_lines_tool(
    filepath: str,
    start: Optional[int] = None,
    end: Optional[int] = None,
    line_numbers: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """
    Extract specific lines from a file.

    Args:
        filepath: Path to file
        start: Start line number (1-indexed, inclusive)
        end: End line number (1-indexed, inclusive)
        line_numbers: Specific lines to extract (e.g., [1, 5, 10])

    Returns:
        Dictionary with:
        - lines: Extracted lines with line numbers
        - count: Number of lines extracted
        - filepath: Path to file

    Examples:
        # First 10 lines
        extract_lines_tool("file.txt", start=1, end=10)

        # Specific lines
        extract_lines_tool("file.txt", line_numbers=[1, 5, 10])

        # Lines 100-150
        extract_lines_tool("file.txt", start=100, end=150)
    """
    path = Path(filepath).expanduser()

    if not path.exists():
        return {"error": f"File not found: {filepath}"}

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()

        total_lines = len(all_lines)

        if line_numbers:
            # Extract specific lines
            extracted = []
            for line_num in sorted(set(line_numbers)):
                if 1 <= line_num <= total_lines:
                    extracted.append({"line_number": line_num, "content": all_lines[line_num - 1].rstrip("\n")})
            return {
                "lines": extracted,
                "count": len(extracted),
                "filepath": str(path),
                "total_lines": total_lines,
            }
        else:
            # Extract range
            start_idx = (start or 1) - 1
            end_idx = (end or total_lines)

            if start_idx < 0:
                start_idx = 0
            if end_idx > total_lines:
                end_idx = total_lines

            extracted = [
                {"line_number": i + 1, "content": all_lines[i].rstrip("\n")}
                for i in range(start_idx, end_idx)
            ]

            return {
                "lines": extracted,
                "count": len(extracted),
                "filepath": str(path),
                "total_lines": total_lines,
                "range": f"{start_idx + 1}-{end_idx}",
            }

    except Exception as e:
        return {"error": f"Extract failed: {e}"}


def head_tool(filepath: str, num_lines: int = 10) -> Dict[str, Any]:
    """
    Get first N lines from a file.

    Args:
        filepath: Path to file
        num_lines: Number of lines to show (default: 10)

    Returns:
        Dictionary with lines and line count

    Examples:
        head_tool("file.txt")  # First 10 lines
        head_tool("file.txt", num_lines=20)  # First 20 lines
    """
    return extract_lines_tool(filepath, start=1, end=num_lines)


def tail_tool(filepath: str, num_lines: int = 10) -> Dict[str, Any]:
    """
    Get last N lines from a file.

    Args:
        filepath: Path to file
        num_lines: Number of lines to show (default: 10)

    Returns:
        Dictionary with lines and line count

    Examples:
        tail_tool("file.txt")  # Last 10 lines
        tail_tool("file.txt", num_lines=20)  # Last 20 lines
    """
    path = Path(filepath).expanduser()

    if not path.exists():
        return {"error": f"File not found: {filepath}"}

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()

        total_lines = len(all_lines)
        start = max(1, total_lines - num_lines + 1)

        return extract_lines_tool(filepath, start=start, end=total_lines)

    except Exception as e:
        return {"error": f"Tail failed: {e}"}
