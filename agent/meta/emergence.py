"""Capability Emergence Tracking - Detect when recursive design creates new capabilities.

This module tracks agent genealogy and identifies emergence patterns where
agents designed by other agents achieve capabilities their parents didn't have.

Emergence signals:
  - New tools discovered during task execution
  - Success on task types parent couldn't handle
  - Lower cost/iterations than parent
  - Novel problem-solving approaches
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentGenealogy:
    """Tracks agent lineage and design history."""

    agent_id: str
    parent_agent_id: Optional[str]
    grandparent_id: Optional[str]
    designer_agent_id: Optional[str]
    generation: int  # 0 = original, 1 = designed by original, etc.
    design_timestamp: float
    capabilities_gained: List[str]  # New capabilities vs parent
    capabilities_lost: List[str]  # Capabilities no longer available
    emergence_score: float  # 0.0-1.0 metric of emergence

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentGenealogy":
        """Create from dictionary."""
        return cls(**data)


@dataclass(frozen=True)
class EmergenceEvent:
    """Single emergence event in agent genealogy."""

    event_id: str
    agent_id: str
    parent_agent_id: Optional[str]
    event_type: str  # "new_tool", "task_success", "cost_improvement", "approach_discovery"
    description: str
    impact_score: float  # 0.0-1.0
    timestamp: float
    task_that_triggered: str
    evidence: Dict[str, Any]


class EmergenceTracker:
    """Tracks capability emergence in recursive agent design."""

    def __init__(self, db_path: Optional[str] = None):
        """Initialize tracker.

        Args:
            db_path: Path to SQLite database.
        """
        if db_path is None:
            from hercules_constants import get_hercules_home

            hercules_home = Path(get_hercules_home())
            db_path = str(hercules_home / "meta" / "emergence_tracker.db")

        self.db_path = db_path
        self._ensure_db()

    def _ensure_db(self):
        """Create database and schema."""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS genealogy (
                    agent_id TEXT PRIMARY KEY,
                    parent_agent_id TEXT,
                    grandparent_id TEXT,
                    designer_agent_id TEXT,
                    generation INTEGER,
                    design_timestamp REAL,
                    capabilities_gained TEXT,
                    capabilities_lost TEXT,
                    emergence_score REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS emergence_events (
                    event_id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    parent_agent_id TEXT,
                    event_type TEXT,
                    description TEXT,
                    impact_score REAL,
                    timestamp REAL,
                    task_that_triggered TEXT,
                    evidence TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(agent_id) REFERENCES genealogy(agent_id)
                )
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_parent
                ON genealogy(parent_agent_id)
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_generation
                ON genealogy(generation)
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_emergence_score
                ON genealogy(emergence_score DESC)
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_event_agent
                ON emergence_events(agent_id)
            """
            )
            conn.commit()

    def record_agent_genealogy(
        self, genealogy: AgentGenealogy
    ) -> None:
        """Record agent lineage information.

        Args:
            genealogy: AgentGenealogy record.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO genealogy (
                        agent_id, parent_agent_id, grandparent_id,
                        designer_agent_id, generation, design_timestamp,
                        capabilities_gained, capabilities_lost, emergence_score
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        genealogy.agent_id,
                        genealogy.parent_agent_id,
                        genealogy.grandparent_id,
                        genealogy.designer_agent_id,
                        genealogy.generation,
                        genealogy.design_timestamp,
                        json.dumps(genealogy.capabilities_gained),
                        json.dumps(genealogy.capabilities_lost),
                        genealogy.emergence_score,
                    ),
                )
                conn.commit()
            logger.debug(
                "Recorded genealogy for agent %s (gen %d, parent %s)",
                genealogy.agent_id,
                genealogy.generation,
                genealogy.parent_agent_id,
            )
        except Exception as e:
            logger.error(
                "Failed to record genealogy: %s", e, exc_info=True
            )

    def record_emergence_event(
        self, event: EmergenceEvent
    ) -> None:
        """Record emergence event.

        Args:
            event: EmergenceEvent record.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO emergence_events (
                        event_id, agent_id, parent_agent_id, event_type,
                        description, impact_score, timestamp,
                        task_that_triggered, evidence
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        event.event_id,
                        event.agent_id,
                        event.parent_agent_id,
                        event.event_type,
                        event.description,
                        event.impact_score,
                        event.timestamp,
                        event.task_that_triggered,
                        json.dumps(event.evidence),
                    ),
                )
                conn.commit()
            logger.info(
                "Recorded emergence event: %s for agent %s (impact %.2f)",
                event.event_type,
                event.agent_id,
                event.impact_score,
            )
        except Exception as e:
            logger.error(
                "Failed to record emergence event: %s", e, exc_info=True
            )

    def detect_emergence(
        self,
        agent_id: str,
        parent_agent_id: Optional[str],
        new_capabilities: List[str],
        parent_capabilities: List[str],
        performance_vs_parent: Dict[str, Any],
    ) -> List[EmergenceEvent]:
        """Detect emergence signals from agent vs parent comparison.

        Args:
            agent_id: ID of new agent.
            parent_agent_id: ID of parent agent.
            new_capabilities: Tools/capabilities available to new agent.
            parent_capabilities: Tools/capabilities parent had.
            performance_vs_parent: Performance metrics comparison.

        Returns:
            List of detected emergence events.
        """
        events: List[EmergenceEvent] = []
        timestamp = time.time()

        # Check for new tools
        new_tools = set(new_capabilities) - set(parent_capabilities)
        if new_tools:
            import uuid

            event_id = str(uuid.uuid4())
            events.append(
                EmergenceEvent(
                    event_id=event_id,
                    agent_id=agent_id,
                    parent_agent_id=parent_agent_id,
                    event_type="new_tool",
                    description=f"Gained new tools: {', '.join(new_tools)}",
                    impact_score=min(0.5, len(new_tools) * 0.1),
                    timestamp=timestamp,
                    task_that_triggered="initialization",
                    evidence={"new_tools": list(new_tools)},
                )
            )

        # Check for cost improvements
        parent_cost = performance_vs_parent.get("parent_avg_cost", float("inf"))
        child_cost = performance_vs_parent.get("child_avg_cost", parent_cost)

        if child_cost < parent_cost * 0.7:  # 30% improvement
            import uuid

            event_id = str(uuid.uuid4())
            improvement_pct = (1 - child_cost / parent_cost) * 100
            events.append(
                EmergenceEvent(
                    event_id=event_id,
                    agent_id=agent_id,
                    parent_agent_id=parent_agent_id,
                    event_type="cost_improvement",
                    description=f"Cost improved by {improvement_pct:.1f}%",
                    impact_score=min(0.4, improvement_pct / 100),
                    timestamp=timestamp,
                    task_that_triggered="cost_optimization",
                    evidence={
                        "parent_cost": parent_cost,
                        "child_cost": child_cost,
                        "improvement_pct": improvement_pct,
                    },
                )
            )

        # Check for success rate improvements
        parent_success = performance_vs_parent.get("parent_success_rate", 0.5)
        child_success = performance_vs_parent.get("child_success_rate", 0.5)

        if child_success > parent_success + 0.1:  # 10% improvement
            import uuid

            event_id = str(uuid.uuid4())
            events.append(
                EmergenceEvent(
                    event_id=event_id,
                    agent_id=agent_id,
                    parent_agent_id=parent_agent_id,
                    event_type="task_success",
                    description=(
                        f"Success rate improved from {parent_success:.1%} "
                        f"to {child_success:.1%}"
                    ),
                    impact_score=min(0.5, (child_success - parent_success)),
                    timestamp=timestamp,
                    task_that_triggered="general_improvement",
                    evidence={
                        "parent_success": parent_success,
                        "child_success": child_success,
                    },
                )
            )

        return events

    def get_agent_lineage(self, agent_id: str) -> List[AgentGenealogy]:
        """Get complete lineage of agent (chain to root).

        Args:
            agent_id: Agent ID.

        Returns:
            List of genealogy records from agent back to root.
        """
        lineage: List[AgentGenealogy] = []

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row

                current_id = agent_id
                visited = set()

                while current_id and current_id not in visited:
                    visited.add(current_id)

                    row = conn.execute(
                        "SELECT * FROM genealogy WHERE agent_id = ?",
                        (current_id,),
                    ).fetchone()

                    if not row:
                        break

                    gen = AgentGenealogy(
                        agent_id=row["agent_id"],
                        parent_agent_id=row["parent_agent_id"],
                        grandparent_id=row["grandparent_id"],
                        designer_agent_id=row["designer_agent_id"],
                        generation=row["generation"],
                        design_timestamp=row["design_timestamp"],
                        capabilities_gained=json.loads(
                            row["capabilities_gained"] or "[]"
                        ),
                        capabilities_lost=json.loads(
                            row["capabilities_lost"] or "[]"
                        ),
                        emergence_score=row["emergence_score"],
                    )
                    lineage.append(gen)

                    current_id = row["parent_agent_id"]
        except Exception as e:
            logger.error(
                "Failed to get lineage: %s", e, exc_info=True
            )

        return lineage

    def get_emergence_frontier(self) -> List[Tuple[str, float]]:
        """Get agents at emergence frontier (highest emergence scores).

        Returns:
            List of (agent_id, emergence_score) sorted by score DESC.
        """
        results = []

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row

                rows = conn.execute(
                    """
                    SELECT agent_id, emergence_score
                    FROM genealogy
                    WHERE emergence_score > 0
                    ORDER BY emergence_score DESC
                    LIMIT 20
                """
                ).fetchall()

                results = [(row["agent_id"], row["emergence_score"]) for row in rows]
        except Exception as e:
            logger.error(
                "Failed to get emergence frontier: %s", e, exc_info=True
            )

        return results

    def get_agent_tree(self, root_agent_id: str) -> Dict[str, Any]:
        """Get tree of all agents descended from root.

        Returns:
            Nested dict structure of agent genealogy.
        """
        tree_data = {
            "agent_id": root_agent_id,
            "children": [],
            "emergence_score": 0.0,
        }

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row

                # Get root info
                root = conn.execute(
                    "SELECT * FROM genealogy WHERE agent_id = ?",
                    (root_agent_id,),
                ).fetchone()

                if root:
                    tree_data["emergence_score"] = root["emergence_score"]

                # Recursively get children
                def add_children(parent_id: str, parent_node: Dict[str, Any]):
                    rows = conn.execute(
                        "SELECT * FROM genealogy WHERE parent_agent_id = ?",
                        (parent_id,),
                    ).fetchall()

                    for row in rows:
                        child_node = {
                            "agent_id": row["agent_id"],
                            "generation": row["generation"],
                            "emergence_score": row["emergence_score"],
                            "children": [],
                        }
                        parent_node["children"].append(child_node)
                        add_children(row["agent_id"], child_node)

                add_children(root_agent_id, tree_data)
        except Exception as e:
            logger.error(
                "Failed to get agent tree: %s", e, exc_info=True
            )

        return tree_data
