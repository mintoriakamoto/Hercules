"""Persistent knowledge store for facts learned during agent conversations.

This module maintains a SQLite-backed knowledge base that:
  - Stores learnable facts extracted from agent interactions
  - Associates facts with confidence scores (0.0-1.0)
  - Tracks timestamps and source turns for fact aging/pruning
  - Enables retrieval of relevant knowledge by topic or semantic query
  - Auto-prunes low-confidence or outdated facts

Schema:
  - knowledge_base: (id, session_id, topic, fact, confidence, created_at, source_turn, last_verified)
  - fact_references: (id, fact_id, referenced_at, context) — tracks usage for adaptive prioritization
  - meta: (key, value) — schema version and other metadata

Confidence scoring:
  - 1.0: Verified facts from code, tests, or explicit confirmation
  - 0.7-0.9: High-confidence inferences from reliable sources
  - 0.4-0.7: Medium-confidence observations from user feedback
  - 0.0-0.4: Low-confidence speculative facts that may need verification

Pruning rules:
  - Facts with confidence < 0.3 after 7 days are removed
  - Facts not referenced for 30 days are downgraded 0.1 points
  - Never prune explicitly confirmed facts (confidence > 0.95)
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from hercules_constants import get_hercules_home

logger = logging.getLogger(__name__)

_DB_LOCK = threading.Lock()
_KNOWLEDGE_DB_VERSION = 1
_CONFIDENCE_THRESHOLD_PRUNE = 0.3
_DAYS_TO_PRUNE = 7
_DAYS_TO_DOWNGRADE = 30
_DOWNGRADE_AMOUNT = 0.1


@dataclass(frozen=True)
class KnownFact:
    """A learned fact with metadata and confidence score."""

    fact_id: int
    session_id: str
    topic: str
    fact: str
    confidence: float
    created_at: str
    source_turn: int
    last_verified: str
    reference_count: int = 0


def _utc_now() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _db_path() -> Path:
    """Return the path to the knowledge base SQLite file."""
    return get_hercules_home() / "knowledge_base.db"


def _connect() -> sqlite3.Connection:
    """Open a connection to the knowledge base with proper settings."""
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Create or verify knowledge base schema."""
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
        CREATE TABLE IF NOT EXISTS knowledge_base (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            topic TEXT NOT NULL,
            fact TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 0.5,
            created_at TEXT NOT NULL,
            source_turn INTEGER NOT NULL,
            last_verified TEXT NOT NULL,
            UNIQUE(session_id, topic, fact)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS fact_references (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fact_id INTEGER NOT NULL,
            referenced_at TEXT NOT NULL,
            context TEXT,
            FOREIGN KEY(fact_id) REFERENCES knowledge_base(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_knowledge_session_topic
        ON knowledge_base(session_id, topic)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_knowledge_confidence
        ON knowledge_base(confidence DESC)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_fact_references_fact_id
        ON fact_references(fact_id, referenced_at DESC)
        """
    )
    conn.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', ?)",
        (str(_KNOWLEDGE_DB_VERSION),),
    )
    conn.execute(
        "INSERT OR IGNORE INTO meta(key, value) VALUES ('created_at', ?)",
        (_utc_now(),),
    )
    conn.commit()


def store_fact(
    session_id: str,
    topic: str,
    fact: str,
    confidence: float = 0.5,
    source_turn: int = 0,
) -> int:
    """Store a learned fact in the knowledge base.

    Args:
        session_id: Session where fact was learned
        topic: Topic/category for the fact (e.g., "codebase", "user_preference")
        fact: The actual fact text
        confidence: Confidence score (0.0-1.0, default 0.5)
        source_turn: Turn number where fact was learned

    Returns:
        The ID of the stored fact
    """
    confidence = max(0.0, min(1.0, confidence))
    now = _utc_now()

    with _DB_LOCK:
        conn = _connect()
        try:
            cursor = conn.execute(
                """
                INSERT OR REPLACE INTO knowledge_base
                (session_id, topic, fact, confidence, created_at, source_turn, last_verified)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, topic, fact, confidence, now, source_turn, now),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()


def lookup_knowledge(
    session_id: str,
    topic: Optional[str] = None,
    query: Optional[str] = None,
    min_confidence: float = 0.4,
    limit: int = 10,
) -> List[KnownFact]:
    """Retrieve relevant knowledge from the store.

    Args:
        session_id: Session ID to query from
        topic: Optional topic filter (exact match)
        query: Optional keyword search in fact text
        min_confidence: Only return facts with this confidence or higher
        limit: Maximum number of facts to return

    Returns:
        List of KnownFact objects sorted by (confidence DESC, created_at DESC)
    """
    with _DB_LOCK:
        conn = _connect()
        try:
            sql = """
                SELECT
                    k.id, k.session_id, k.topic, k.fact, k.confidence,
                    k.created_at, k.source_turn, k.last_verified,
                    COUNT(f.id) as reference_count
                FROM knowledge_base k
                LEFT JOIN fact_references f ON k.id = f.fact_id
                WHERE k.session_id = ? AND k.confidence >= ?
            """
            params: List[Any] = [session_id, min_confidence]

            if topic:
                sql += " AND k.topic = ?"
                params.append(topic)

            if query:
                # Simple keyword search (substring match)
                sql += " AND k.fact LIKE ?"
                params.append(f"%{query}%")

            sql += """
                GROUP BY k.id
                ORDER BY k.confidence DESC, k.created_at DESC
                LIMIT ?
            """
            params.append(limit)

            cursor = conn.execute(sql, params)
            facts = []
            for row in cursor:
                facts.append(
                    KnownFact(
                        fact_id=row["id"],
                        session_id=row["session_id"],
                        topic=row["topic"],
                        fact=row["fact"],
                        confidence=row["confidence"],
                        created_at=row["created_at"],
                        source_turn=row["source_turn"],
                        last_verified=row["last_verified"],
                        reference_count=row["reference_count"],
                    )
                )
            return facts
        finally:
            conn.close()


def update_confidence(fact_id: int, new_confidence: float) -> bool:
    """Update a fact's confidence score.

    Args:
        fact_id: ID of fact to update
        new_confidence: New confidence value (0.0-1.0)

    Returns:
        True if update succeeded, False if fact not found
    """
    new_confidence = max(0.0, min(1.0, new_confidence))
    now = _utc_now()

    with _DB_LOCK:
        conn = _connect()
        try:
            cursor = conn.execute(
                """
                UPDATE knowledge_base
                SET confidence = ?, last_verified = ?
                WHERE id = ?
                """,
                (new_confidence, now, fact_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()


def record_fact_reference(fact_id: int, context: Optional[str] = None) -> None:
    """Record that a fact was referenced/used.

    This tracks usage patterns for adaptive prioritization and prevents
    premature pruning of frequently-used facts.

    Args:
        fact_id: ID of fact that was referenced
        context: Optional context about why it was referenced
    """
    with _DB_LOCK:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO fact_references (fact_id, referenced_at, context)
                VALUES (?, ?, ?)
                """,
                (fact_id, _utc_now(), context),
            )
            conn.commit()
        finally:
            conn.close()


def prune_old_facts() -> Tuple[int, int]:
    """Remove low-confidence or outdated facts.

    Pruning rules:
      - Facts with confidence < THRESHOLD after DAYS_TO_PRUNE days are removed
      - Facts not referenced for DAYS_TO_DOWNGRADE days have confidence reduced
      - Never prune explicitly confirmed facts (confidence >= 0.95)

    Returns:
        Tuple of (facts_removed, facts_downgraded)
    """
    now = datetime.now(timezone.utc)
    cutoff_for_removal = (now - timedelta(days=_DAYS_TO_PRUNE)).isoformat()
    cutoff_for_downgrade = (now - timedelta(days=_DAYS_TO_DOWNGRADE)).isoformat()

    with _DB_LOCK:
        conn = _connect()
        try:
            # Remove low-confidence old facts
            cursor = conn.execute(
                """
                DELETE FROM knowledge_base
                WHERE confidence < ? AND created_at < ? AND confidence < 0.95
                """,
                (_CONFIDENCE_THRESHOLD_PRUNE, cutoff_for_removal),
            )
            removed_count = cursor.rowcount

            # Downgrade facts not referenced recently
            conn.execute(
                """
                UPDATE knowledge_base
                SET confidence = MAX(0, confidence - ?)
                WHERE confidence < 0.95
                AND NOT EXISTS (
                    SELECT 1 FROM fact_references
                    WHERE fact_id = knowledge_base.id AND referenced_at > ?
                )
                """,
                (_DOWNGRADE_AMOUNT, cutoff_for_downgrade),
            )
            downgraded_count = cursor.rowcount

            conn.commit()
            return removed_count, downgraded_count
        finally:
            conn.close()


def get_statistics(session_id: Optional[str] = None) -> Dict[str, Any]:
    """Get statistics about stored knowledge.

    Args:
        session_id: Optional session ID to filter by

    Returns:
        Dictionary with fact counts and confidence distribution
    """
    with _DB_LOCK:
        conn = _connect()
        try:
            if session_id:
                cursor = conn.execute(
                    """
                    SELECT
                        COUNT(*) as total_facts,
                        AVG(confidence) as avg_confidence,
                        MIN(confidence) as min_confidence,
                        MAX(confidence) as max_confidence,
                        COUNT(DISTINCT topic) as unique_topics,
                        COUNT(DISTINCT session_id) as unique_sessions
                    FROM knowledge_base
                    WHERE session_id = ?
                    """,
                    (session_id,),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT
                        COUNT(*) as total_facts,
                        AVG(confidence) as avg_confidence,
                        MIN(confidence) as min_confidence,
                        MAX(confidence) as max_confidence,
                        COUNT(DISTINCT topic) as unique_topics,
                        COUNT(DISTINCT session_id) as unique_sessions
                    FROM knowledge_base
                    """
                )

            row = cursor.fetchone()
            if row:
                return {
                    "total_facts": row["total_facts"] or 0,
                    "avg_confidence": row["avg_confidence"] or 0.0,
                    "min_confidence": row["min_confidence"] or 0.0,
                    "max_confidence": row["max_confidence"] or 0.0,
                    "unique_topics": row["unique_topics"] or 0,
                    "unique_sessions": row["unique_sessions"] or 0,
                }
            return {
                "total_facts": 0,
                "avg_confidence": 0.0,
                "min_confidence": 0.0,
                "max_confidence": 0.0,
                "unique_topics": 0,
                "unique_sessions": 0,
            }
        finally:
            conn.close()


def clear_session(session_id: str) -> int:
    """Clear all knowledge for a specific session.

    Args:
        session_id: Session ID to clear

    Returns:
        Number of facts removed
    """
    with _DB_LOCK:
        conn = _connect()
        try:
            cursor = conn.execute(
                "DELETE FROM knowledge_base WHERE session_id = ?",
                (session_id,),
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()
