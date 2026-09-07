#!/usr/bin/env python3
"""
Data Transform Tool - Simple JSON and data format conversions and operations.

Convert between JSON, CSV, YAML and perform basic data operations.
"""

import json
import csv
import io
from pathlib import Path
from typing import Dict, Any, List, Optional


def json_to_csv_tool(json_file: str, output_file: Optional[str] = None) -> Dict[str, Any]:
    """
    Convert JSON array to CSV.

    Args:
        json_file: Path to JSON file (must be array of objects)
        output_file: Optional output CSV file path (default: prints to console)

    Returns:
        Dictionary with:
        - success: Whether conversion succeeded
        - rows: Number of rows converted
        - columns: Column names
        - csv_content: CSV data (if no output_file)
        - output_file: Path to written file (if output_file provided)

    Examples:
        # Convert JSON to CSV
        json_to_csv_tool("data.json")

        # Save to file
        json_to_csv_tool("data.json", "data.csv")
    """
    path = Path(json_file).expanduser()

    if not path.exists():
        return {"error": f"File not found: {json_file}", "success": False}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON: {e}", "success": False}
    except Exception as e:
        return {"error": f"Cannot read file: {e}", "success": False}

    if not isinstance(data, list):
        return {
            "error": "JSON must be an array of objects",
            "success": False,
        }

    if not data:
        return {"error": "JSON array is empty", "success": False, "rows": 0}

    try:
        # Get all keys from all objects
        all_keys = set()
        for item in data:
            if isinstance(item, dict):
                all_keys.update(item.keys())

        columns = sorted(list(all_keys))

        # Convert to CSV
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        writer.writerows(data)

        csv_content = output.getvalue()

        if output_file:
            out_path = Path(output_file).expanduser()
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(csv_content)
            return {
                "success": True,
                "rows": len(data),
                "columns": columns,
                "output_file": str(out_path),
            }
        else:
            return {
                "success": True,
                "rows": len(data),
                "columns": columns,
                "csv_content": csv_content[:1000],  # First 1000 chars
                "note": "Showing first 1000 chars of output",
            }

    except Exception as e:
        return {"error": f"Conversion failed: {e}", "success": False}


def csv_to_json_tool(csv_file: str, output_file: Optional[str] = None) -> Dict[str, Any]:
    """
    Convert CSV to JSON array.

    Args:
        csv_file: Path to CSV file
        output_file: Optional output JSON file path

    Returns:
        Dictionary with:
        - success: Whether conversion succeeded
        - rows: Number of rows converted
        - columns: Column names
        - json_content: JSON data (if no output_file)
        - output_file: Path to written file (if output_file provided)

    Examples:
        # Convert CSV to JSON
        csv_to_json_tool("data.csv")

        # Save to file
        csv_to_json_tool("data.csv", "data.json")
    """
    path = Path(csv_file).expanduser()

    if not path.exists():
        return {"error": f"File not found: {csv_file}", "success": False}

    try:
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if not rows:
            return {"error": "CSV is empty", "success": False, "rows": 0}

        columns = list(rows[0].keys()) if rows else []
        json_data = json.dumps(rows, indent=2)

        if output_file:
            out_path = Path(output_file).expanduser()
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(json_data)
            return {
                "success": True,
                "rows": len(rows),
                "columns": columns,
                "output_file": str(out_path),
            }
        else:
            return {
                "success": True,
                "rows": len(rows),
                "columns": columns,
                "json_content": json_data[:1000],  # First 1000 chars
                "note": "Showing first 1000 chars of output",
            }

    except Exception as e:
        return {"error": f"Conversion failed: {e}", "success": False}


def json_format_tool(json_file: str, indent: int = 2, sort_keys: bool = False) -> Dict[str, Any]:
    """
    Format and validate JSON file.

    Args:
        json_file: Path to JSON file
        indent: Indentation level (default: 2)
        sort_keys: Sort object keys alphabetically (default: False)

    Returns:
        Dictionary with:
        - valid: Whether JSON is valid
        - formatted: Formatted JSON (first 2000 chars)
        - size_before: Original file size
        - size_after: Formatted size
        - error: Error message if invalid

    Examples:
        # Format a JSON file
        json_format_tool("messy.json")

        # Sort keys and pretty-print
        json_format_tool("data.json", sort_keys=True)
    """
    path = Path(json_file).expanduser()

    if not path.exists():
        return {"error": f"File not found: {json_file}", "valid": False}

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            size_before = len(content)

        data = json.loads(content)
        formatted = json.dumps(data, indent=indent, sort_keys=sort_keys)
        size_after = len(formatted)

        return {
            "valid": True,
            "formatted": formatted[:2000],  # First 2000 chars
            "size_before": size_before,
            "size_after": size_after,
            "note": "Showing first 2000 chars of formatted output",
            "file": str(path),
        }

    except json.JSONDecodeError as e:
        return {
            "valid": False,
            "error": f"Invalid JSON: {e}",
            "line": e.lineno,
            "column": e.colno,
        }
    except Exception as e:
        return {"valid": False, "error": f"Error: {e}"}


def json_query_tool(json_file: str, key_path: str) -> Dict[str, Any]:
    """
    Query JSON file by key path (simple dot notation).

    Args:
        json_file: Path to JSON file
        key_path: Key path using dot notation (e.g., "user.profile.name")

    Returns:
        Dictionary with:
        - found: Whether key was found
        - value: The value at the key path
        - type: Type of value
        - error: Error message if not found

    Examples:
        # Get nested value
        json_query_tool("data.json", "user.profile.email")

        # Get array element
        json_query_tool("items.json", "items.0.name")
    """
    path = Path(json_file).expanduser()

    if not path.exists():
        return {"error": f"File not found: {json_file}", "found": False}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON: {e}", "found": False}
    except Exception as e:
        return {"error": f"Cannot read file: {e}", "found": False}

    # Navigate the key path
    keys = key_path.split(".")
    current = data

    try:
        for key in keys:
            # Try integer index for arrays
            if isinstance(current, list):
                try:
                    idx = int(key)
                    current = current[idx]
                except (ValueError, IndexError):
                    return {"error": f"Invalid array index: {key}", "found": False}
            elif isinstance(current, dict):
                current = current[key]
            else:
                return {
                    "error": f"Cannot navigate through {type(current).__name__}",
                    "found": False,
                }

        return {
            "found": True,
            "value": current if not isinstance(current, (dict, list)) else str(current)[:500],
            "type": type(current).__name__,
            "key_path": key_path,
        }

    except KeyError:
        return {"error": f"Key not found: {key_path}", "found": False}
    except Exception as e:
        return {"error": f"Query failed: {e}", "found": False}
