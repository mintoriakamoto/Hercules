"""Explicit audit log for agent decisions and tool calls."""

import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AuditEntry:
    """Single audit log entry."""

    def __init__(
        self,
        timestamp: str,
        action: str,
        tool_name: Optional[str] = None,
        args: Optional[Dict] = None,
        result: Optional[Dict] = None,
        status: str = "success",
        error: Optional[str] = None,
    ):
        self.timestamp = timestamp
        self.action = action
        self.tool_name = tool_name
        self.args = args or {}
        self.result = result or {}
        self.status = status
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "timestamp": self.timestamp,
            "action": self.action,
            "tool_name": self.tool_name,
            "args": self.args,
            "result": self.result,
            "status": self.status,
            "error": self.error,
        }


class AuditLog:
    """Thread-safe audit log for agent decisions."""

    def __init__(self, session_id: str, log_dir: Optional[Path] = None):
        """Initialize audit log.

        Args:
            session_id: Session identifier
            log_dir: Optional directory to write audit logs
        """
        self.session_id = session_id
        self.log_dir = log_dir
        self.entries: List[AuditEntry] = []
        self._lock = threading.Lock()

    def record_tool_call(
        self,
        tool_name: str,
        args: Dict[str, Any],
        result: Dict[str, Any],
        status: str = "success",
        error: Optional[str] = None,
    ) -> None:
        """Log a tool invocation."""
        entry = AuditEntry(
            timestamp=datetime.now().isoformat(),
            action="tool_call",
            tool_name=tool_name,
            args=args,
            result=result,
            status=status,
            error=error,
        )
        with self._lock:
            self.entries.append(entry)

    def record_decision(self, decision: str, context: Dict[str, Any]) -> None:
        """Log an agent decision."""
        entry = AuditEntry(
            timestamp=datetime.now().isoformat(),
            action="decision",
            args=context,
            status="recorded",
        )
        with self._lock:
            self.entries.append(entry)

    def get_entries(self) -> List[AuditEntry]:
        """Get all audit entries."""
        with self._lock:
            return list(self.entries)

    def get_recovery_chains(self) -> List[tuple]:
        """Get (fail → succeed) chains for curator analysis."""
        with self._lock:
            chains = []
            for i, entry in enumerate(self.entries):
                if entry.status == "failed" and entry.tool_name:
                    # Look for next success of same tool
                    for j in range(i + 1, len(self.entries)):
                        if (
                            self.entries[j].tool_name == entry.tool_name
                            and self.entries[j].status == "success"
                        ):
                            chains.append((entry, self.entries[j]))
                            break
            return chains

    def write_to_file(self) -> Optional[Path]:
        """Write audit log to file."""
        if not self.log_dir:
            return None

        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            log_file = self.log_dir / f"audit_{self.session_id}.jsonl"

            with self._lock:
                with open(log_file, "w", encoding="utf-8") as f:
                    for entry in self.entries:
                        f.write(json.dumps(entry.to_dict()) + "\n")

            return log_file
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
            return None
