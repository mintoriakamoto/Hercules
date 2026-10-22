"""State management with checkpoint protocol."""

import json
import hashlib
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional
from pathlib import Path
import sqlite3
from datetime import datetime


@dataclass
class Checkpoint:
    """Formal checkpoint with integrity verification."""
    checkpoint_id: str
    step: int
    timestamp: str
    state_hash: str
    state_data: Dict[str, Any]
    metadata: Dict[str, Any]

    def verify_integrity(self) -> bool:
        """Verify checkpoint has not been corrupted."""
        computed_hash = hashlib.sha256(
            json.dumps(self.state_data, sort_keys=True).encode()
        ).hexdigest()
        return computed_hash == self.state_hash


class StateManager:
    """Manages agent state with checkpoints and persistence."""

    def __init__(self, db_path: str = "agent_state.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database for checkpoints."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    checkpoint_id TEXT PRIMARY KEY,
                    step INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    state_hash TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    event TEXT NOT NULL,
                    data_json TEXT NOT NULL
                )
            """)
            conn.commit()

    def save_checkpoint(
        self,
        step: int,
        state_data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Save checkpoint with integrity hash."""
        checkpoint_id = f"ckpt_{step}_{int(datetime.now().timestamp()*1000)}"

        state_json = json.dumps(state_data, default=str, sort_keys=True)
        state_hash = hashlib.sha256(state_json.encode()).hexdigest()

        checkpoint = Checkpoint(
            checkpoint_id=checkpoint_id,
            step=step,
            timestamp=datetime.now().isoformat(),
            state_hash=state_hash,
            state_data=state_data,
            metadata=metadata or {},
        )

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO checkpoints 
                (checkpoint_id, step, timestamp, state_hash, state_json, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    checkpoint.checkpoint_id,
                    checkpoint.step,
                    checkpoint.timestamp,
                    checkpoint.state_hash,
                    state_json,
                    json.dumps(checkpoint.metadata, default=str),
                ),
            )
            conn.commit()

        return checkpoint_id

    def load_checkpoint(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """Load and verify checkpoint integrity."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM checkpoints WHERE checkpoint_id = ?",
                (checkpoint_id,),
            )
            row = cursor.fetchone()

            if not row:
                return None

            checkpoint = Checkpoint(
                checkpoint_id=row[0],
                step=row[1],
                timestamp=row[2],
                state_hash=row[3],
                state_data=json.loads(row[4]),
                metadata=json.loads(row[5]),
            )

            # Verify integrity
            if not checkpoint.verify_integrity():
                raise ValueError(f"Checkpoint {checkpoint_id} integrity check failed")

            return checkpoint

    def log_event(self, event_type: str, data: Dict[str, Any]):
        """Log event to immutable audit trail."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO audit_log (timestamp, event, data_json) VALUES (?, ?, ?)",
                (
                    datetime.now().isoformat(),
                    event_type,
                    json.dumps(data, default=str),
                ),
            )
            conn.commit()

    def get_audit_log(self, event_type: Optional[str] = None) -> list:
        """Retrieve audit log (immutable history)."""
        with sqlite3.connect(self.db_path) as conn:
            if event_type:
                cursor = conn.execute(
                    "SELECT * FROM audit_log WHERE event = ? ORDER BY id ASC",
                    (event_type,),
                )
            else:
                cursor = conn.execute("SELECT * FROM audit_log ORDER BY id ASC")

            return [
                {
                    "id": row[0],
                    "timestamp": row[1],
                    "event": row[2],
                    "data": json.loads(row[3]),
                }
                for row in cursor.fetchall()
            ]

    def list_checkpoints(self) -> list:
        """List all checkpoints."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT checkpoint_id, step, timestamp FROM checkpoints")
            return [
                {"checkpoint_id": row[0], "step": row[1], "timestamp": row[2]}
                for row in cursor.fetchall()
            ]


__all__ = ["StateManager", "Checkpoint"]
