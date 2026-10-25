"""Incremental tool output compression — compress results immediately after retrieval.

Rather than leaving large tool outputs in context, this module:
  - Compresses tool results immediately after retrieval
  - Agent sees full output (passes to model)
  - System stores compressed reference
  - Re-fetch decompresses on-demand (cheaper than re-executing)

Trade-offs:
  - ~100ms decompress delay vs. tool re-execution cost (often 5-30s)
  - Useful for file reads, API responses, search results
  - Not for streaming or interactive results

Storage:
  - SQLite: (tool_name, args_hash, result_hash, compressed_data, timestamp)
  - Compression: zlib for text, JSON for structured
  - Retention: 24 hours or session end

Example:
  result = file_read("/home/user/large_file.py")  # 100KB
  agent sees full output
  compress_tool_output("file_read", {"path": "..."}, result)
  system stores: 5KB compressed, can decompress when needed
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import threading
import time
import zlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from hercules_constants import get_hercules_home

logger = logging.getLogger(__name__)

_DB_LOCK = threading.Lock()
_TOOL_OUTPUT_CACHE_VERSION = 1
_COMPRESSION_THRESHOLD = 5000  # Only compress if > 5KB
_CACHE_RETENTION_HOURS = 24


@dataclass
class CachedToolOutput:
    """A compressed tool output ready for decompression."""

    tool_name: str
    args_hash: str
    result_hash: str
    compressed_size: int
    original_size: int
    compression_ratio: float
    timestamp: str


def _hash_json(obj: Any) -> str:
    """Hash a JSON-serializable object."""
    try:
        json_str = json.dumps(obj, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode()).hexdigest()[:16]
    except (TypeError, ValueError):
        # Fallback for non-JSON-able objects
        return hashlib.sha256(str(obj).encode()).hexdigest()[:16]


def _utc_now() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _db_path() -> Path:
    """Return path to tool output cache database."""
    return get_hercules_home() / "tool_output_cache.db"


def _connect() -> sqlite3.Connection:
    """Open connection to tool output cache."""
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Create or verify tool output cache schema."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tool_output_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tool_name TEXT NOT NULL,
            args_hash TEXT NOT NULL,
            result_hash TEXT NOT NULL,
            compressed_data BLOB NOT NULL,
            original_size INTEGER NOT NULL,
            compressed_size INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            accessed_count INTEGER DEFAULT 0,
            last_accessed TEXT,
            UNIQUE(tool_name, args_hash, result_hash)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_tool_output_tool_args
        ON tool_output_cache(tool_name, args_hash)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_tool_output_timestamp
        ON tool_output_cache(timestamp DESC)
        """
    )
    conn.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', ?)",
        (str(_TOOL_OUTPUT_CACHE_VERSION),),
    )
    conn.commit()


def should_cache(tool_name: str, result: Any) -> bool:
    """Check if a tool result should be cached.

    Args:
        tool_name: Name of the tool
        result: The result to potentially cache

    Returns:
        True if caching is appropriate
    """
    # Don't cache streaming or interactive tools
    streaming_tools = {"stream", "websocket", "realtime", "subscribe"}
    if any(s in tool_name.lower() for s in streaming_tools):
        return False

    # Estimate size
    try:
        if isinstance(result, str):
            size = len(result.encode())
        elif isinstance(result, bytes):
            size = len(result)
        else:
            size = len(json.dumps(result, default=str).encode())
    except (TypeError, ValueError):
        return False

    # Only cache large outputs
    return size >= _COMPRESSION_THRESHOLD


def compress_tool_output(
    tool_name: str,
    args: Any,
    result: Any,
) -> bool:
    """Compress and cache a tool output.

    Args:
        tool_name: Name of the tool that produced this
        args: Arguments passed to the tool
        result: The result to compress

    Returns:
        True if caching succeeded
    """
    if not should_cache(tool_name, result):
        return False

    args_hash = _hash_json(args)
    result_hash = _hash_json(result)

    # Serialize result
    try:
        if isinstance(result, str):
            data = result.encode()
        elif isinstance(result, bytes):
            data = result
        else:
            data = json.dumps(result, default=str).encode()
    except (TypeError, ValueError):
        logger.warning("Failed to serialize result from %s", tool_name)
        return False

    original_size = len(data)

    # Compress
    try:
        compressed = zlib.compress(data, level=6)
    except Exception as e:
        logger.warning("Failed to compress %s output: %s", tool_name, e)
        return False

    compressed_size = len(compressed)
    compression_ratio = compressed_size / original_size if original_size > 0 else 0

    # Only store if compression actually helps
    if compression_ratio >= 0.95:
        logger.debug("Skipped caching %s: poor compression ratio", tool_name)
        return False

    with _DB_LOCK:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO tool_output_cache
                (tool_name, args_hash, result_hash, compressed_data, original_size, compressed_size, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (tool_name, args_hash, result_hash, compressed, original_size, compressed_size, _utc_now()),
            )
            conn.commit()
            logger.debug(
                f"Cached {tool_name} output: {original_size} -> {compressed_size} bytes "
                f"({compression_ratio:.1%} ratio)"
            )
            return True
        except Exception as e:
            logger.error("Failed to cache %s output: %s", tool_name, e)
            return False
        finally:
            conn.close()


def get_cached_output(tool_name: str, args: Any) -> Optional[Any]:
    """Retrieve and decompress a cached tool output.

    Args:
        tool_name: Name of the tool
        args: Arguments that were passed

    Returns:
        Decompressed result, or None if not cached
    """
    args_hash = _hash_json(args)

    with _DB_LOCK:
        conn = _connect()
        try:
            cursor = conn.execute(
                """
                SELECT compressed_data FROM tool_output_cache
                WHERE tool_name = ? AND args_hash = ?
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                (tool_name, args_hash),
            )
            row = cursor.fetchone()
            if not row:
                return None

            # Decompress
            try:
                data = zlib.decompress(row["compressed_data"])
                # Try JSON first, then string
                try:
                    return json.loads(data)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    return data.decode()
            except Exception as e:
                logger.error("Failed to decompress cached %s output: %s", tool_name, e)
                return None
        finally:
            conn.close()


def estimate_cache_savings() -> Dict[str, Any]:
    """Estimate disk and compute savings from caching.

    Returns:
        Dictionary with savings statistics
    """
    with _DB_LOCK:
        conn = _connect()
        try:
            cursor = conn.execute(
                """
                SELECT
                    COUNT(*) as cached_items,
                    SUM(original_size) as total_original,
                    SUM(compressed_size) as total_compressed,
                    AVG(compression_ratio) as avg_compression
                FROM (
                    SELECT
                        original_size,
                        compressed_size,
                        CAST(compressed_size AS FLOAT) / original_size as compression_ratio
                    FROM tool_output_cache
                )
                """
            )
            row = cursor.fetchone()
            if row and row["cached_items"]:
                total_original = row["total_original"] or 0
                total_compressed = row["total_compressed"] or 0
                disk_saved = total_original - total_compressed

                # Rough estimate: re-execution would take 5-30s, consuming ~0.001-0.01 API cost
                api_calls_avoided = row["cached_items"]
                estimated_api_savings = api_calls_avoided * 0.005  # Rough middle estimate

                return {
                    "cached_items": row["cached_items"],
                    "disk_saved_bytes": disk_saved,
                    "compression_ratio": row["avg_compression"] or 0.0,
                    "estimated_api_calls_avoided": api_calls_avoided,
                    "estimated_api_cost_saved": estimated_api_savings,
                }
            return {
                "cached_items": 0,
                "disk_saved_bytes": 0,
                "compression_ratio": 0.0,
                "estimated_api_calls_avoided": 0,
                "estimated_api_cost_saved": 0.0,
            }
        finally:
            conn.close()


def cleanup_old_cache(max_age_hours: int = _CACHE_RETENTION_HOURS) -> int:
    """Remove cached outputs older than max_age_hours.

    Args:
        max_age_hours: Age threshold in hours

    Returns:
        Number of items removed
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=max_age_hours)).isoformat()

    with _DB_LOCK:
        conn = _connect()
        try:
            cursor = conn.execute(
                "DELETE FROM tool_output_cache WHERE timestamp < ?",
                (cutoff,),
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()
