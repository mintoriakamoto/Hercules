#!/usr/bin/env python3
"""
Directory Statistics Tool - Get summary information about directories and files.

Analyze directory contents, file types, and disk usage.
"""

import os
from pathlib import Path
from collections import defaultdict
from typing import Dict, Any, List


def directory_stats_tool(
    path: str = ".",
    max_depth: int = 2,
    include_hidden: bool = False,
) -> Dict[str, Any]:
    """
    Get statistics about a directory.

    Args:
        path: Directory path (default: current directory)
        max_depth: Maximum recursion depth (default: 2)
        include_hidden: Include hidden files/dirs (default: False)

    Returns:
        Dictionary with:
        - total_files: Total number of files
        - total_dirs: Total number of directories
        - total_size_bytes: Total size in bytes
        - by_extension: File count and size by file extension
        - by_type: Breakdown by file type (source, config, media, etc)
        - largest_files: Top 10 largest files
        - largest_dirs: Top 5 largest directories

    Examples:
        # Analyze current directory
        directory_stats_tool()

        # Analyze specific directory
        directory_stats_tool("/home/user/projects", max_depth=3)
    """
    base_path = Path(path).expanduser()

    if not base_path.exists():
        return {"error": f"Path not found: {path}"}

    if not base_path.is_dir():
        return {"error": f"Not a directory: {path}"}

    file_stats = defaultdict(lambda: {"count": 0, "size": 0})
    type_stats = defaultdict(lambda: {"count": 0, "size": 0})
    all_files = []
    dir_sizes = {}
    total_files = 0
    total_dirs = 0
    total_size = 0

    # File type classifier
    def classify_file(name: str) -> str:
        ext = Path(name).suffix.lower()
        if ext in {".py", ".js", ".ts", ".go", ".rs", ".java", ".cpp", ".c", ".h"}:
            return "source_code"
        elif ext in {".json", ".yaml", ".yml", ".toml", ".xml", ".ini", ".conf"}:
            return "config"
        elif ext in {".txt", ".md", ".rst", ".org"}:
            return "documentation"
        elif ext in {".jpg", ".jpeg", ".png", ".gif", ".svg", ".ico"}:
            return "images"
        elif ext in {".mp4", ".avi", ".mov", ".mkv"}:
            return "video"
        elif ext in {".mp3", ".wav", ".flac", ".aac"}:
            return "audio"
        elif ext in {".zip", ".tar", ".gz", ".7z", ".rar"}:
            return "archive"
        elif ext in {".pdf", ".doc", ".docx", ".xls", ".xlsx"}:
            return "documents"
        else:
            return "other"

    try:
        for root, dirs, files in os.walk(base_path):
            # Check depth
            depth = root[len(str(base_path)):].count(os.sep)
            if depth > max_depth:
                dirs.clear()
                continue

            # Filter hidden
            if not include_hidden:
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                files = [f for f in files if not f.startswith(".")]

            total_dirs += len(dirs)
            total_files += len(files)

            for filename in files:
                filepath = os.path.join(root, filename)
                try:
                    size = os.path.getsize(filepath)
                    total_size += size

                    # Track by extension
                    ext = Path(filename).suffix.lower() or "no_extension"
                    file_stats[ext]["count"] += 1
                    file_stats[ext]["size"] += size

                    # Track by type
                    ftype = classify_file(filename)
                    type_stats[ftype]["count"] += 1
                    type_stats[ftype]["size"] += size

                    all_files.append((filepath, size))

                except OSError:
                    pass

            # Calculate directory sizes
            try:
                dir_size = sum(os.path.getsize(os.path.join(root, f))
                             for f in files if os.path.isfile(os.path.join(root, f)))
                if dir_size > 0:
                    dir_sizes[root] = dir_size
            except OSError:
                pass

    except Exception as e:
        return {"error": f"Error scanning directory: {e}"}

    # Top 10 largest files
    all_files.sort(key=lambda x: x[1], reverse=True)
    largest_files = [
        {"path": str(Path(p).relative_to(base_path)), "size_bytes": s}
        for p, s in all_files[:10]
    ]

    # Top 5 largest directories
    sorted_dirs = sorted(dir_sizes.items(), key=lambda x: x[1], reverse=True)
    largest_dirs = [
        {"path": str(Path(d).relative_to(base_path)), "size_bytes": s}
        for d, s in sorted_dirs[:5]
    ]

    # Format sizes nicely
    def format_size(bytes_size: int) -> str:
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if bytes_size < 1024:
                return f"{bytes_size:.1f}{unit}"
            bytes_size /= 1024
        return f"{bytes_size:.1f}PB"

    return {
        "path": str(base_path),
        "total_files": total_files,
        "total_dirs": total_dirs,
        "total_size_bytes": total_size,
        "total_size_human": format_size(total_size),
        "by_extension": {
            ext: {
                "count": stats["count"],
                "size_bytes": stats["size"],
                "size_human": format_size(stats["size"]),
            }
            for ext, stats in sorted(
                file_stats.items(), key=lambda x: x[1]["size"], reverse=True
            )[:10]  # Top 10 extensions
        },
        "by_type": {
            ftype: {
                "count": stats["count"],
                "size_bytes": stats["size"],
                "size_human": format_size(stats["size"]),
            }
            for ftype, stats in sorted(
                type_stats.items(), key=lambda x: x[1]["size"], reverse=True
            )
        },
        "largest_files": largest_files,
        "largest_dirs": largest_dirs,
    }


def tree_view_tool(
    path: str = ".",
    max_depth: int = 3,
    ignore_hidden: bool = True,
    max_items: int = 50,
) -> Dict[str, Any]:
    """
    Generate a tree view of directory structure.

    Args:
        path: Directory path
        max_depth: Maximum depth to show (default: 3)
        ignore_hidden: Skip hidden files/dirs (default: True)
        max_items: Maximum total items to show (default: 50)

    Returns:
        Dictionary with:
        - tree: ASCII tree representation
        - truncated: Whether output was truncated

    Examples:
        # Show directory tree
        tree_view_tool("./src")

        # Show deeper tree
        tree_view_tool(".", max_depth=5)
    """
    base_path = Path(path).expanduser()

    if not base_path.exists():
        return {"error": f"Path not found: {path}"}

    if not base_path.is_dir():
        return {"error": f"Not a directory: {path}"}

    lines = [str(base_path) + "/"]
    item_count = 0
    truncated = False

    def add_tree(directory: Path, prefix: str = "", depth: int = 0):
        nonlocal item_count, truncated

        if depth > max_depth or item_count >= max_items:
            return

        try:
            entries = sorted(directory.iterdir())
            if ignore_hidden:
                entries = [e for e in entries if not e.name.startswith(".")]

            for i, entry in enumerate(entries):
                if item_count >= max_items:
                    truncated = True
                    return

                is_last = i == len(entries) - 1
                current_prefix = "└── " if is_last else "├── "
                next_prefix = "    " if is_last else "│   "

                if entry.is_dir():
                    lines.append(prefix + current_prefix + entry.name + "/")
                else:
                    size = entry.stat().st_size
                    lines.append(prefix + current_prefix + f"{entry.name} ({size}B)")

                item_count += 1

                if entry.is_dir() and depth < max_depth:
                    add_tree(entry, prefix + next_prefix, depth + 1)

        except PermissionError:
            pass

    add_tree(base_path)

    return {
        "tree": "\n".join(lines[:max_items * 2]),  # Limit output size
        "truncated": truncated,
        "path": str(base_path),
        "items_shown": len(lines),
    }
