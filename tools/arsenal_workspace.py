"""Arsenal workspace: IDE-like environment for dangerous operations.

Philosophy: ALLOW by default (like IDE), but TRACK everything
- Full filesystem access (within workspace)
- Full network access (but logged)
- Full process execution
- BUT: Everything is recorded, audited, and reversible

Like VS Code or Vim: you can do anything, but everything you do
is saved to history and can be undone.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class WorkspaceChange:
    """Track a single change in workspace."""
    timestamp: datetime
    operation: str  # "create", "modify", "delete", "execute"
    path: str

    # Before/after state
    before: Optional[str] = None  # File content before
    after: Optional[str] = None   # File content after

    # For executions
    command: Optional[str] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    exit_code: Optional[int] = None

    # Network operations
    network_target: Optional[str] = None
    network_port: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "operation": self.operation,
            "path": self.path,
            "before": self.before[:100] if self.before else None,
            "after": self.after[:100] if self.after else None,
            "command": self.command,
            "exit_code": self.exit_code,
            "network_target": self.network_target,
        }


@dataclass
class WorkspaceSnapshot:
    """Point-in-time snapshot of workspace state."""
    name: str
    timestamp: datetime
    description: str
    file_hash: str  # Hash of all files
    changes_count: int

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "timestamp": self.timestamp.isoformat(),
            "description": self.description,
            "file_hash": self.file_hash,
            "changes_count": self.changes_count,
        }


class ArsenalWorkspace:
    """IDE-like workspace for arsenal operations."""

    def __init__(self, workspace_dir: Path, history_dir: Path):
        self.workspace_dir = workspace_dir
        self.history_dir = history_dir
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir.mkdir(parents=True, exist_ok=True)

        # Current operation tracking
        self.changes: list[WorkspaceChange] = []
        self.snapshots: dict[str, WorkspaceSnapshot] = {}

        # Load existing snapshots
        self._load_snapshots()

    @contextmanager
    def track_operation(self, operation_name: str):
        """Track an operation - all changes recorded."""
        self.changes = []  # Reset changes for this operation
        start_time = datetime.now()

        try:
            yield self
        finally:
            # Save operation to history
            self._save_operation(operation_name, start_time)

    def create_file(self, relative_path: str, content: str) -> Path:
        """Create file in workspace (tracked)."""
        file_path = self.workspace_dir / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)

        # Track change
        self.changes.append(WorkspaceChange(
            timestamp=datetime.now(),
            operation="create",
            path=relative_path,
            after=content
        ))

        logger.info(f"Created: {relative_path}")
        return file_path

    def modify_file(self, relative_path: str, content: str) -> Path:
        """Modify file in workspace (tracked)."""
        file_path = self.workspace_dir / relative_path

        # Track before/after
        before = file_path.read_text() if file_path.exists() else None
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)

        self.changes.append(WorkspaceChange(
            timestamp=datetime.now(),
            operation="modify",
            path=relative_path,
            before=before,
            after=content
        ))

        logger.info(f"Modified: {relative_path}")
        return file_path

    def delete_file(self, relative_path: str) -> None:
        """Delete file from workspace (tracked)."""
        file_path = self.workspace_dir / relative_path

        # Track before deletion
        before = file_path.read_text() if file_path.exists() else None
        if file_path.exists():
            file_path.unlink()

        self.changes.append(WorkspaceChange(
            timestamp=datetime.now(),
            operation="delete",
            path=relative_path,
            before=before
        ))

        logger.info(f"Deleted: {relative_path}")

    def execute_command(self, command: list[str], cwd: Optional[str] = None) -> dict:
        """Execute command in workspace (tracked, full output)."""
        exec_cwd = self.workspace_dir / cwd if cwd else self.workspace_dir

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            cwd=exec_cwd,
            timeout=300  # 5 minute timeout
        )

        # Track execution
        self.changes.append(WorkspaceChange(
            timestamp=datetime.now(),
            operation="execute",
            path=str(exec_cwd),
            command=" ".join(command),
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.returncode
        ))

        logger.info(f"Executed: {' '.join(command)} (exit: {result.returncode})")

        return {
            "command": " ".join(command),
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "success": result.returncode == 0
        }

    def network_operation(self, target: str, port: int, operation: str) -> dict:
        """Track network operations (full access logged)."""
        self.changes.append(WorkspaceChange(
            timestamp=datetime.now(),
            operation="network",
            path=f"{target}:{port}",
            command=operation,
            network_target=target,
            network_port=port
        ))

        logger.info(f"Network: {target}:{port} - {operation}")

        return {
            "target": target,
            "port": port,
            "operation": operation,
            "logged": True
        }

    def snapshot(self, name: str, description: str = "") -> WorkspaceSnapshot:
        """Create snapshot of current workspace state."""
        # Hash all files
        file_hash = self._hash_workspace()

        # Create snapshot
        snap = WorkspaceSnapshot(
            name=name,
            timestamp=datetime.now(),
            description=description,
            file_hash=file_hash,
            changes_count=len(self.changes)
        )

        # Store snapshot metadata
        self.snapshots[name] = snap
        self._save_snapshots()

        # Copy workspace state to snapshots dir
        snap_dir = self.history_dir / "snapshots" / name
        if snap_dir.exists():
            shutil.rmtree(snap_dir)
        shutil.copytree(self.workspace_dir, snap_dir)

        logger.info(f"Snapshot: {name} (hash: {file_hash[:16]}...)")
        return snap

    def rollback(self, snapshot_name: str) -> bool:
        """Rollback workspace to snapshot (undo all changes)."""
        if snapshot_name not in self.snapshots:
            logger.error(f"Snapshot not found: {snapshot_name}")
            return False

        snap_dir = self.history_dir / "snapshots" / snapshot_name
        if not snap_dir.exists():
            logger.error(f"Snapshot files not found: {snapshot_name}")
            return False

        # Clear workspace
        if self.workspace_dir.exists():
            shutil.rmtree(self.workspace_dir)

        # Restore from snapshot
        shutil.copytree(snap_dir, self.workspace_dir)

        logger.info(f"Rolled back to: {snapshot_name}")

        # Track rollback
        self.changes.append(WorkspaceChange(
            timestamp=datetime.now(),
            operation="rollback",
            path=snapshot_name,
            command=f"rollback to {snapshot_name}"
        ))

        return True

    def get_history(self, limit: int = 100) -> list[dict]:
        """Get operation history (IDE-like change log)."""
        return [c.to_dict() for c in self.changes[-limit:]]

    def get_diff(self, snapshot_name: str) -> dict:
        """Get diff between current state and snapshot."""
        if snapshot_name not in self.snapshots:
            return {"error": "Snapshot not found"}

        snap_dir = self.history_dir / "snapshots" / snapshot_name

        # Compare file counts
        current_files = set(f.relative_to(self.workspace_dir)
                           for f in self.workspace_dir.rglob("*") if f.is_file())
        snap_files = set(f.relative_to(snap_dir)
                        for f in snap_dir.rglob("*") if f.is_file())

        return {
            "snapshot": snapshot_name,
            "current_timestamp": datetime.now().isoformat(),
            "snapshot_timestamp": self.snapshots[snapshot_name].timestamp.isoformat(),
            "files_added": len(current_files - snap_files),
            "files_removed": len(snap_files - current_files),
            "files_modified": len(current_files & snap_files),
            "details": {
                "added": [str(f) for f in (current_files - snap_files)],
                "removed": [str(f) for f in (snap_files - current_files)],
            }
        }

    def _hash_workspace(self) -> str:
        """Compute hash of entire workspace."""
        hasher = hashlib.sha256()

        for file_path in sorted(self.workspace_dir.rglob("*")):
            if file_path.is_file():
                hasher.update(file_path.read_bytes())

        return hasher.hexdigest()

    def _save_operation(self, operation_name: str, start_time: datetime):
        """Save operation to history log."""
        op_file = self.history_dir / "operations.jsonl"

        op_record = {
            "name": operation_name,
            "timestamp": start_time.isoformat(),
            "duration_seconds": (datetime.now() - start_time).total_seconds(),
            "changes": len(self.changes),
            "changes_detail": [c.to_dict() for c in self.changes],
        }

        with open(op_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(op_record) + "\n")

    def _load_snapshots(self):
        """Load existing snapshots."""
        snap_file = self.history_dir / "snapshots.json"
        if snap_file.exists():
            data = json.loads(snap_file.read_text())
            for snap_data in data:
                snap = WorkspaceSnapshot(
                    name=snap_data["name"],
                    timestamp=datetime.fromisoformat(snap_data["timestamp"]),
                    description=snap_data.get("description", ""),
                    file_hash=snap_data.get("file_hash", ""),
                    changes_count=snap_data.get("changes_count", 0)
                )
                self.snapshots[snap.name] = snap

    def _save_snapshots(self):
        """Save snapshot metadata."""
        snap_file = self.history_dir / "snapshots.json"
        snap_file.write_text(json.dumps(
            [s.to_dict() for s in self.snapshots.values()],
            indent=2
        ))


# Singleton instance
_WORKSPACE: ArsenalWorkspace | None = None


def get_arsenal_workspace() -> ArsenalWorkspace:
    """Get or create arsenal workspace."""
    global _WORKSPACE
    if _WORKSPACE is None:
        workspace_dir = Path.home() / ".hercules" / ".arsenal_workspace"
        history_dir = Path.home() / ".hercules" / ".arsenal_history"
        _WORKSPACE = ArsenalWorkspace(workspace_dir, history_dir)
    return _WORKSPACE


def run_arsenal_operation(
    operation_name: str,
    func: Callable[[ArsenalWorkspace], Any]
) -> dict:
    """Execute arsenal operation in tracked workspace."""
    workspace = get_arsenal_workspace()

    with workspace.track_operation(operation_name):
        result = func(workspace)

    return {
        "operation": operation_name,
        "result": result,
        "changes": len(workspace.changes),
        "history_available": True,
        "rollback_available": True,
    }
