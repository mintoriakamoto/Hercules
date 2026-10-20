"""Adaptive memory manager — learns and prioritizes context based on access patterns.

This module tracks which compressed context levels are accessed during agent
execution and builds a score-based model:

  - Track every fetch_context_level() call: which level, what query, success
  - Maintain reference scores for each context item
  - High-referential-density context: preserve during compression
  - Low-density context: compress aggressively

The system learns:
  - Which context types are queried frequently
  - Which queries succeed vs fail (relevance feedback)
  - Topic distribution of agent's work
  - Optimal compression ratios per context type

Integration points:
  - compress_context() checks scores before pruning
  - fetch_context_level() updates scores after successful retrieval
  - Training: scores are persisted per session and transferred across turns
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from hercules_constants import get_hercules_home

logger = logging.getLogger(__name__)

_DB_LOCK = threading.Lock()
_MEMORY_SCORE_VERSION = 1
_MIN_REFERENCE_SCORE = 0.1  # Score below this: eligible for aggressive compression


@dataclass
class ContextItemScore:
    """Score of a context item based on access patterns."""

    item_id: str  # Unique identifier (hash of content)
    context_type: str  # "message", "summary", "cluster", "theme"
    compression_level: int  # 0-3
    reference_count: int  # Times this item was accessed
    relevance_score: float  # 0.0-1.0, higher = more frequently accessed
    last_accessed: str  # ISO timestamp
    created_at: str  # ISO timestamp
    mean_query_length: int  # Average length of queries that matched


def _utc_now() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _db_path() -> Path:
    """Return path to adaptive memory scores database."""
    return get_hercules_home() / "memory_scores.db"


def _connect() -> sqlite3.Connection:
    """Open connection to memory scores database."""
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Create or verify memory scores schema."""
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
        CREATE TABLE IF NOT EXISTS context_item_scores (
            item_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            context_type TEXT NOT NULL,
            compression_level INTEGER NOT NULL,
            reference_count INTEGER DEFAULT 0,
            relevance_score REAL DEFAULT 0.5,
            last_accessed TEXT NOT NULL,
            created_at TEXT NOT NULL,
            mean_query_length INTEGER DEFAULT 0
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS access_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            item_id TEXT NOT NULL,
            accessed_at TEXT NOT NULL,
            query_length INTEGER,
            query_success INTEGER DEFAULT 0,
            context_level INTEGER NOT NULL,
            FOREIGN KEY(item_id) REFERENCES context_item_scores(item_id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_context_item_scores_session
        ON context_item_scores(session_id, relevance_score DESC)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_access_patterns_session
        ON access_patterns(session_id, accessed_at DESC)
        """
    )
    conn.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', ?)",
        (str(_MEMORY_SCORE_VERSION),),
    )
    conn.commit()


def record_context_access(
    session_id: str,
    item_id: str,
    context_type: str,
    compression_level: int,
    query_length: int = 0,
    success: bool = True,
) -> None:
    """Record that a context item was accessed.

    Args:
        session_id: Session ID
        item_id: Unique identifier of context item
        context_type: Type of context ("message", "summary", "cluster", "theme")
        compression_level: Compression level (0-3)
        query_length: Length of the query that matched this item
        success: Whether the access was successful/relevant
    """
    now = _utc_now()

    with _DB_LOCK:
        conn = _connect()
        try:
            # Check if item already has a score
            cursor = conn.execute(
                "SELECT relevance_score, reference_count, mean_query_length FROM context_item_scores WHERE item_id = ?",
                (item_id,),
            )
            existing = cursor.fetchone()

            if existing:
                # Update existing score
                old_score = existing["relevance_score"]
                old_count = existing["reference_count"]
                old_mean_query = existing["mean_query_length"]

                # EMA update: new_score = 0.9 * old_score + 0.1 * success
                new_score = 0.9 * old_score + 0.1 * (1.0 if success else 0.5)

                # Update mean query length
                new_count = old_count + 1
                new_mean_query = (
                    (old_mean_query * old_count + query_length) // new_count
                    if new_count > 0
                    else 0
                )

                conn.execute(
                    """
                    UPDATE context_item_scores
                    SET reference_count = ?, relevance_score = ?, last_accessed = ?, mean_query_length = ?
                    WHERE item_id = ?
                    """,
                    (new_count, new_score, now, new_mean_query, item_id),
                )
            else:
                # Create new score
                conn.execute(
                    """
                    INSERT INTO context_item_scores
                    (item_id, session_id, context_type, compression_level, reference_count, relevance_score, last_accessed, created_at, mean_query_length)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item_id,
                        session_id,
                        context_type,
                        compression_level,
                        1,
                        1.0 if success else 0.5,
                        now,
                        now,
                        query_length,
                    ),
                )

            # Record access pattern
            conn.execute(
                """
                INSERT INTO access_patterns
                (session_id, item_id, accessed_at, query_length, query_success, context_level)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session_id, item_id, now, query_length, 1 if success else 0, compression_level),
            )

            conn.commit()
        finally:
            conn.close()


def get_item_score(item_id: str) -> Optional[ContextItemScore]:
    """Retrieve the score for a context item.

    Args:
        item_id: Item identifier

    Returns:
        ContextItemScore or None if not found
    """
    with _DB_LOCK:
        conn = _connect()
        try:
            cursor = conn.execute(
                "SELECT * FROM context_item_scores WHERE item_id = ?",
                (item_id,),
            )
            row = cursor.fetchone()
            if row:
                return ContextItemScore(
                    item_id=row["item_id"],
                    context_type=row["context_type"],
                    compression_level=row["compression_level"],
                    reference_count=row["reference_count"],
                    relevance_score=row["relevance_score"],
                    last_accessed=row["last_accessed"],
                    created_at=row["created_at"],
                    mean_query_length=row["mean_query_length"],
                )
            return None
        finally:
            conn.close()


def get_session_scores(session_id: str, limit: int = 100) -> List[ContextItemScore]:
    """Get all scores for a session, sorted by relevance.

    Args:
        session_id: Session ID
        limit: Maximum scores to return

    Returns:
        List of ContextItemScore objects, highest relevance first
    """
    with _DB_LOCK:
        conn = _connect()
        try:
            cursor = conn.execute(
                """
                SELECT * FROM context_item_scores
                WHERE session_id = ?
                ORDER BY relevance_score DESC
                LIMIT ?
                """,
                (session_id, limit),
            )
            scores = []
            for row in cursor:
                scores.append(
                    ContextItemScore(
                        item_id=row["item_id"],
                        context_type=row["context_type"],
                        compression_level=row["compression_level"],
                        reference_count=row["reference_count"],
                        relevance_score=row["relevance_score"],
                        last_accessed=row["last_accessed"],
                        created_at=row["created_at"],
                        mean_query_length=row["mean_query_length"],
                    )
                )
            return scores
        finally:
            conn.close()


def get_low_priority_items(
    session_id: str,
    threshold: float = _MIN_REFERENCE_SCORE,
) -> List[str]:
    """Get IDs of low-priority items that could be compressed.

    Args:
        session_id: Session ID
        threshold: Score threshold (items below this are low-priority)

    Returns:
        List of item IDs eligible for aggressive compression
    """
    with _DB_LOCK:
        conn = _connect()
        try:
            cursor = conn.execute(
                """
                SELECT item_id FROM context_item_scores
                WHERE session_id = ? AND relevance_score < ?
                ORDER BY relevance_score ASC
                """,
                (session_id, threshold),
            )
            return [row["item_id"] for row in cursor]
        finally:
            conn.close()


def get_high_priority_items(
    session_id: str,
    threshold: float = 0.7,
) -> List[str]:
    """Get IDs of high-priority items that should be preserved.

    Args:
        session_id: Session ID
        threshold: Score threshold (items above this are high-priority)

    Returns:
        List of item IDs that should be preserved
    """
    with _DB_LOCK:
        conn = _connect()
        try:
            cursor = conn.execute(
                """
                SELECT item_id FROM context_item_scores
                WHERE session_id = ? AND relevance_score >= ?
                ORDER BY relevance_score DESC
                """,
                (session_id, threshold),
            )
            return [row["item_id"] for row in cursor]
        finally:
            conn.close()


def get_access_statistics(session_id: str) -> Dict[str, Any]:
    """Get access pattern statistics for a session.

    Args:
        session_id: Session ID

    Returns:
        Dictionary with access statistics
    """
    with _DB_LOCK:
        conn = _connect()
        try:
            # Overall stats
            cursor = conn.execute(
                """
                SELECT
                    COUNT(DISTINCT item_id) as unique_items,
                    COUNT(*) as total_accesses,
                    AVG(query_success) as success_rate
                FROM access_patterns
                WHERE session_id = ?
                """,
                (session_id,),
            )
            row = cursor.fetchone()
            overall = {
                "unique_items": row["unique_items"] or 0,
                "total_accesses": row["total_accesses"] or 0,
                "success_rate": row["success_rate"] or 0.0,
            }

            # Per-level stats
            cursor = conn.execute(
                """
                SELECT
                    context_level,
                    COUNT(*) as access_count,
                    AVG(query_success) as success_rate
                FROM access_patterns
                WHERE session_id = ?
                GROUP BY context_level
                ORDER BY context_level
                """,
                (session_id,),
            )
            by_level = {}
            for row in cursor:
                by_level[f"level_{row['context_level']}"] = {
                    "access_count": row["access_count"] or 0,
                    "success_rate": row["success_rate"] or 0.0,
                }

            return {"overall": overall, "by_level": by_level}
        finally:
            conn.close()


def estimate_compression_impact(session_id: str) -> Dict[str, float]:
    """Estimate the impact of compressing low-priority items.

    Returns analysis of:
      - How many low-priority items could be compressed
      - Estimated token savings
      - Risk (success rate of compressed items)

    Args:
        session_id: Session ID

    Returns:
        Dictionary with impact estimates
    """
    low_priority = get_low_priority_items(session_id)
    stats = get_access_statistics(session_id)

    overall_success = stats["overall"]["success_rate"]
    unique_items = stats["overall"]["unique_items"]

    compression_candidates = len(low_priority)
    compression_percent = (compression_candidates / unique_items * 100) if unique_items > 0 else 0

    # Rough estimate: 4 chars per token, each compressed item saves ~100 tokens
    estimated_savings = compression_candidates * 100

    return {
        "candidates_for_compression": compression_candidates,
        "compression_percent": compression_percent,
        "estimated_token_savings": estimated_savings,
        "risk_low_success_rate": overall_success < 0.7,
        "recommendation": "compress" if overall_success > 0.8 else "defer",
    }


def clear_session(session_id: str) -> int:
    """Clear all scores for a session.

    Args:
        session_id: Session ID

    Returns:
        Number of items cleared
    """
    with _DB_LOCK:
        conn = _connect()
        try:
            cursor = conn.execute(
                "DELETE FROM context_item_scores WHERE session_id = ?",
                (session_id,),
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()
