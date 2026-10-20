"""Architecture Learning Registry - Learn from successful designs.

Maintains a database of task-agent pairings and their success rates.
Enables similarity-based lookup to reuse successful architectures.

Database schema:
  (task_embedding, task_type, agent_config, success_rate, avg_cost, timestamp)

Indexing:
  - Semantic similarity on task embeddings
  - Task type categories
  - Success rate (for ranking)
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ArchitectureRecord:
    """Record of a task-agent pairing and its success."""

    task_id: str
    task_description: str
    task_type: str
    agent_config: Dict[str, Any]
    success: bool
    success_rate: float
    avg_cost_tokens: float
    iterations_used: int
    model_used: str
    toolsets_used: List[str]
    timestamp: float
    parent_config: Optional[Dict[str, Any]] = None
    designer_agent_id: Optional[str] = None
    emergence_score: float = 0.0  # Capability emergence metric

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        # Serialize nested dicts
        data["agent_config"] = json.dumps(self.agent_config)
        if self.parent_config:
            data["parent_config"] = json.dumps(self.parent_config)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArchitectureRecord":
        """Create from dictionary with JSON deserialization."""
        data = data.copy()
        if isinstance(data.get("agent_config"), str):
            data["agent_config"] = json.loads(data["agent_config"])
        if isinstance(data.get("parent_config"), str):
            data["parent_config"] = json.loads(data["parent_config"])
        if isinstance(data.get("toolsets_used"), str):
            data["toolsets_used"] = json.loads(data["toolsets_used"])
        return cls(**data)


class ArchitectureRegistry:
    """Learns from successful task-agent pairings."""

    def __init__(self, db_path: Optional[str] = None):
        """Initialize registry.

        Args:
            db_path: Path to SQLite database. Defaults to ~/.hercules/registry.db
        """
        if db_path is None:
            from hercules_constants import get_hercules_home

            hercules_home = Path(get_hercules_home())
            db_path = str(hercules_home / "meta" / "architecture_registry.db")

        self.db_path = db_path
        self._ensure_db()

    def _ensure_db(self):
        """Create database and schema if not exists."""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS architecture_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    task_description TEXT NOT NULL,
                    task_type TEXT,
                    agent_config TEXT NOT NULL,
                    parent_config TEXT,
                    success BOOLEAN NOT NULL,
                    success_rate REAL,
                    avg_cost_tokens REAL,
                    iterations_used INTEGER,
                    model_used TEXT NOT NULL,
                    toolsets_used TEXT,
                    timestamp REAL NOT NULL,
                    designer_agent_id TEXT,
                    emergence_score REAL DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_task_type
                ON architecture_records(task_type)
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_success
                ON architecture_records(success, success_rate DESC)
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_model
                ON architecture_records(model_used)
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_timestamp
                ON architecture_records(timestamp DESC)
            """
            )
            conn.commit()

    def record_task_result(
        self,
        record: ArchitectureRecord,
    ) -> None:
        """Record successful or failed task-agent pairing.

        Args:
            record: ArchitectureRecord with task and agent details.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO architecture_records (
                        task_id, task_description, task_type, agent_config,
                        parent_config, success, success_rate, avg_cost_tokens,
                        iterations_used, model_used, toolsets_used, timestamp,
                        designer_agent_id, emergence_score
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        record.task_id,
                        record.task_description,
                        record.task_type,
                        json.dumps(record.agent_config),
                        json.dumps(record.parent_config)
                        if record.parent_config
                        else None,
                        record.success,
                        record.success_rate,
                        record.avg_cost_tokens,
                        record.iterations_used,
                        record.model_used,
                        json.dumps(record.toolsets_used)
                        if record.toolsets_used
                        else None,
                        record.timestamp,
                        record.designer_agent_id,
                        record.emergence_score,
                    ),
                )
                conn.commit()
            logger.debug(
                "Recorded architecture for task %s: success=%s",
                record.task_id,
                record.success,
            )
        except Exception as e:
            logger.error(
                "Failed to record architecture: %s", e, exc_info=True
            )

    def lookup_successful_architecture(
        self, task_description: str, limit: int = 5
    ) -> Optional[Dict[str, Any]]:
        """Look up successful architectures for similar tasks.

        Finds previous successful runs on similar tasks and recommends
        their agent configurations.

        Args:
            task_description: Description of new task.
            limit: Max results to return.

        Returns:
            Agent config from highest-success-rate similar task, or None.
        """
        # Simple keyword-based similarity for now
        keywords = self._extract_keywords(task_description)

        if not keywords:
            # Fallback: return best overall recent config
            return self._get_best_overall_config()

        # Find records with matching keywords
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row

                # Build dynamic LIKE clauses for keywords
                where_clauses = [f"task_description LIKE ?" for _ in keywords]
                like_params = [f"%{kw}%" for kw in keywords]

                query = f"""
                    SELECT agent_config, success_rate, COUNT(*) as count
                    FROM architecture_records
                    WHERE success = 1 AND ({' OR '.join(where_clauses)})
                    GROUP BY agent_config
                    ORDER BY success_rate DESC, count DESC
                    LIMIT 1
                """

                cursor = conn.execute(query, like_params)
                row = cursor.fetchone()

                if row:
                    config = json.loads(row["agent_config"])
                    logger.info(
                        "Found similar successful architecture with "
                        "success_rate=%.2f",
                        row["success_rate"],
                    )
                    return config
        except Exception as e:
            logger.error(
                "Failed to lookup architecture: %s", e, exc_info=True
            )

        return None

    def get_successful_architectures_for_task_type(
        self, task_type: str, limit: int = 10
    ) -> List[Tuple[Dict[str, Any], float]]:
        """Get best architectures for a task type.

        Args:
            task_type: Task type string (e.g., "code_execution").
            limit: Max results.

        Returns:
            List of (agent_config, success_rate) tuples.
        """
        results = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row

                query = """
                    SELECT DISTINCT agent_config, success_rate
                    FROM architecture_records
                    WHERE task_type = ? AND success = 1
                    ORDER BY success_rate DESC
                    LIMIT ?
                """

                cursor = conn.execute(query, (task_type, limit))

                for row in cursor:
                    config = json.loads(row["agent_config"])
                    results.append((config, row["success_rate"]))
        except Exception as e:
            logger.error(
                "Failed to get architectures: %s", e, exc_info=True
            )

        return results

    def get_statistics(self) -> Dict[str, Any]:
        """Get registry statistics.

        Returns:
            Dict with stats like total records, success rate, etc.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row

                # Count records
                total = conn.execute(
                    "SELECT COUNT(*) as count FROM architecture_records"
                ).fetchone()

                successful = conn.execute(
                    "SELECT COUNT(*) as count FROM architecture_records "
                    "WHERE success = 1"
                ).fetchone()

                # Average metrics
                avg_metrics = conn.execute(
                    """
                    SELECT
                        AVG(success_rate) as avg_success,
                        AVG(avg_cost_tokens) as avg_cost,
                        AVG(iterations_used) as avg_iterations
                    FROM architecture_records
                    WHERE success = 1
                """
                ).fetchone()

                # Most common models
                models = conn.execute(
                    """
                    SELECT model_used, COUNT(*) as count
                    FROM architecture_records
                    WHERE success = 1
                    GROUP BY model_used
                    ORDER BY count DESC
                    LIMIT 5
                """
                ).fetchall()

                return {
                    "total_records": total["count"],
                    "successful_records": successful["count"],
                    "overall_success_rate": successful["count"]
                    / total["count"]
                    if total["count"] > 0
                    else 0.0,
                    "avg_success_rate": avg_metrics["avg_success"] or 0.0,
                    "avg_cost_tokens": avg_metrics["avg_cost"] or 0.0,
                    "avg_iterations": avg_metrics["avg_iterations"] or 0.0,
                    "top_models": [
                        {"model": m["model_used"], "count": m["count"]}
                        for m in models
                    ],
                }
        except Exception as e:
            logger.error("Failed to get statistics: %s", e, exc_info=True)
            return {}

    def clear_old_records(self, days: int = 30) -> int:
        """Remove records older than N days.

        Args:
            days: Age threshold in days.

        Returns:
            Number of records deleted.
        """
        try:
            cutoff = time.time() - (days * 86400)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM architecture_records WHERE timestamp < ?",
                    (cutoff,),
                )
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            logger.error(
                "Failed to clear old records: %s", e, exc_info=True
            )
            return 0

    # --- Internal helpers ---

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords for similarity matching."""
        # Simple keyword extraction - in production would use NLP
        stop_words = {
            "a",
            "the",
            "and",
            "or",
            "is",
            "to",
            "of",
            "for",
            "in",
        }
        words = text.lower().split()
        return [
            w for w in words if len(w) > 3 and w not in stop_words
        ][:10]

    def _get_best_overall_config(self) -> Optional[Dict[str, Any]]:
        """Get best overall agent config from history."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row

                query = """
                    SELECT agent_config
                    FROM architecture_records
                    WHERE success = 1
                    ORDER BY success_rate DESC, timestamp DESC
                    LIMIT 1
                """

                row = conn.execute(query).fetchone()

                if row:
                    return json.loads(row["agent_config"])
        except Exception as e:
            logger.error(
                "Failed to get best config: %s", e, exc_info=True
            )

        return None
