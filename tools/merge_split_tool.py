#!/usr/bin/env python3
"""Merge and Split Files Tool - Combine or divide files."""

from pathlib import Path
from typing import Dict, Any, List


def merge_files_tool(
    input_files: List[str],
    output_file: str,
    separator: str = "",
) -> Dict[str, Any]:
    """
    Merge multiple files into one.

    Args:
        input_files: List of file paths to merge
        output_file: Output file path
        separator: Text to insert between files (default: empty)

    Returns:
        Dictionary with:
        - success: Whether merge succeeded
        - files_merged: Number of files merged
        - total_lines: Total lines in output
        - output_file: Path to output file

    Examples:
        merge_files_tool(["a.txt", "b.txt", "c.txt"], "merged.txt")
        merge_files_tool(["file1.txt", "file2.txt"], "output.txt", separator="\\n---\\n")
    """
    output_path = Path(output_file).expanduser()

    try:
        all_lines = []
        files_merged = 0

        for input_file in input_files:
            path = Path(input_file).expanduser()

            if not path.exists():
                return {
                    "error": f"Input file not found: {input_file}",
                    "success": False,
                }

            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                    all_lines.extend(lines)
                    files_merged += 1

                    # Add separator if specified
                    if separator and input_file != input_files[-1]:
                        all_lines.append(separator)
                        if not separator.endswith("\n"):
                            all_lines.append("\n")

            except Exception as e:
                return {
                    "error": f"Cannot read {input_file}: {e}",
                    "success": False,
                }

        # Write output
        with open(output_path, "w", encoding="utf-8") as f:
            f.writelines(all_lines)

        return {
            "success": True,
            "files_merged": files_merged,
            "total_lines": len(all_lines),
            "output_file": str(output_path),
        }

    except Exception as e:
        return {"error": f"Merge failed: {e}", "success": False}


def split_file_tool(
    filepath: str,
    lines_per_file: int,
    output_prefix: str = "",
) -> Dict[str, Any]:
    """
    Split a file into smaller files.

    Args:
        filepath: Path to file to split
        lines_per_file: Number of lines per output file
        output_prefix: Prefix for output files (default: original filename)

    Returns:
        Dictionary with:
        - success: Whether split succeeded
        - files_created: Number of output files
        - total_lines: Total lines processed
        - output_files: List of created files

    Examples:
        # Split into files with 1000 lines each
        split_file_tool("huge.txt", 1000)

        # Split with custom prefix
        split_file_tool("data.csv", 500, output_prefix="chunk_")
    """
    path = Path(filepath).expanduser()

    if not path.exists():
        return {"error": f"File not found: {filepath}", "success": False}

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()

        if not output_prefix:
            output_prefix = path.stem

        output_files = []
        file_num = 1

        for i in range(0, len(all_lines), lines_per_file):
            chunk = all_lines[i : i + lines_per_file]
            output_filename = f"{output_prefix}_{file_num:04d}{path.suffix}"
            output_path = path.parent / output_filename

            with open(output_path, "w", encoding="utf-8") as f:
                f.writelines(chunk)

            output_files.append(str(output_path))
            file_num += 1

        return {
            "success": True,
            "files_created": len(output_files),
            "total_lines": len(all_lines),
            "output_files": output_files,
            "source_file": str(path),
        }

    except Exception as e:
        return {"error": f"Split failed: {e}", "success": False}
