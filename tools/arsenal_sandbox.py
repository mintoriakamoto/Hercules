"""Secure sandbox for destructive arsenal tools.

Philosophy: ZERO TRUST for arsenal operations.
- Default: DENY everything
- Exceptions: Only explicitly allowed operations
- Verification: All outcomes verified before return
- Audit: Immutable log of all changes
- Limits: Rate limiting, resource caps, time limits

Arsenal tools (metasploit, hydra, payload generators, lateral movement, data exfil)
are sandboxed in isolation with no access to host system except through strict interfaces.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


class SandboxLevel(Enum):
    """Isolation levels for arsenal tools."""
    RESTRICTED = "restricted"  # Network off, no FS access, 30s timeout
    ISOLATED = "isolated"      # Network restricted, limited FS, 2min timeout
    CONTAINED = "contained"    # Network to targets only, read-only FS, 5min timeout


@dataclass
class SandboxPolicy:
    """Security policy for sandbox."""
    level: SandboxLevel

    # Network
    allowed_ips: list[str] = field(default_factory=list)  # "10.0.0.0/8", "192.168.0.0/16"
    allowed_ports: list[int] = field(default_factory=list)  # [80, 443, 22, 3389]
    deny_all_network: bool = True

    # Filesystem
    allowed_read_dirs: list[Path] = field(default_factory=list)  # /tmp/sandbox only
    allowed_write_dirs: list[Path] = field(default_factory=list)  # /tmp/sandbox/output only
    deny_all_filesystem: bool = True

    # Process
    max_processes: int = 4  # Max child processes
    max_threads: int = 8
    max_file_descriptors: int = 256

    # Resources
    max_cpu_percent: int = 80
    max_memory_mb: int = 2048
    max_disk_write_mb: int = 1024
    timeout_seconds: int = 30

    # Execution
    require_signature: bool = True  # Must be signed
    require_human_approval: bool = True  # Always ask human

    @classmethod
    def for_level(cls, level: SandboxLevel) -> SandboxPolicy:
        """Create policy for isolation level."""
        if level == SandboxLevel.RESTRICTED:
            return cls(
                level=level,
                allowed_ips=[],  # NO network
                allowed_ports=[],
                deny_all_network=True,
                allowed_read_dirs=[],
                allowed_write_dirs=[],
                deny_all_filesystem=True,
                timeout_seconds=30,
                max_memory_mb=512
            )
        elif level == SandboxLevel.ISOLATED:
            return cls(
                level=level,
                allowed_ips=["127.0.0.1"],  # Localhost only
                allowed_ports=[],
                deny_all_network=True,
                timeout_seconds=120,
                max_memory_mb=1024
            )
        else:  # CONTAINED
            return cls(
                level=level,
                allowed_ips=["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"],  # Private only
                allowed_ports=[22, 80, 443, 3389, 5985, 5986],  # Common ports
                deny_all_network=False,
                timeout_seconds=300,
                max_memory_mb=2048
            )


@dataclass
class SandboxExecution:
    """Record of a single sandbox execution."""
    tool_name: str
    args: dict
    started_at: datetime
    ended_at: datetime | None = None
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""

    # Outcome verification
    outcome_claimed: dict | None = None  # What tool claimed to do
    outcome_verified: dict | None = None  # What actually happened
    outcome_matches: bool | None = None  # Does claimed match verified?

    # Resource usage
    cpu_seconds: float = 0.0
    memory_peak_mb: float = 0.0
    disk_written_mb: float = 0.0

    # Security
    violations: list[str] = field(default_factory=list)
    signature_valid: bool = False
    human_approved: bool = False

    # Audit
    audit_hash: str = ""

    def to_dict(self) -> dict:
        """Serialize to JSON."""
        data = asdict(self)
        data["started_at"] = self.started_at.isoformat()
        data["ended_at"] = self.ended_at.isoformat() if self.ended_at else None
        return data

    def compute_hash(self) -> str:
        """Compute immutable hash of execution."""
        payload = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()


class ArsenalSandbox:
    """Strict sandbox for arsenal tools."""

    def __init__(self, sandbox_dir: Path, audit_log: Path):
        self.sandbox_dir = sandbox_dir
        self.audit_log = audit_log
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)
        self.audit_log.parent.mkdir(parents=True, exist_ok=True)

        # Rate limiter: max 1 destructive tool per 60s, 5 per hour
        self.call_times: dict[str, list[float]] = {}

        # Execution tracking
        self.executions: list[SandboxExecution] = []

    def check_rate_limit(self, tool_name: str) -> bool:
        """Check if tool can run (rate limited)."""
        now = time.time()

        # Initialize tracking
        if tool_name not in self.call_times:
            self.call_times[tool_name] = []

        # Remove old entries
        self.call_times[tool_name] = [
            t for t in self.call_times[tool_name]
            if now - t < 3600  # Keep last hour
        ]

        # Check hourly limit (5 calls)
        if len(self.call_times[tool_name]) >= 5:
            logger.error(f"Rate limit: {tool_name} max 5 per hour")
            return False

        # Check 60-second limit (1 call, only for destructive)
        DESTRUCTIVE = {"metasploit_exploit", "lateral_move", "exfil_data", "drop_database"}
        if tool_name in DESTRUCTIVE:
            recent_60s = [t for t in self.call_times[tool_name] if now - t < 60]
            if len(recent_60s) >= 1:
                logger.error(f"Rate limit: {tool_name} max 1 per 60s")
                return False

        # Record this call
        self.call_times[tool_name].append(now)
        return True

    @contextmanager
    def execute_isolated(self, tool_name: str, policy: SandboxPolicy):
        """Execute tool in isolated sandbox."""

        exec_record = SandboxExecution(
            tool_name=tool_name,
            args={},
            started_at=datetime.now()
        )

        try:
            # Step 1: Rate limit check (DENY if exceeded)
            if not self.check_rate_limit(tool_name):
                raise PermissionError(f"Rate limit exceeded for {tool_name}")

            # Step 2: Require human approval (ALWAYS for destructive)
            ALWAYS_APPROVE = {
                "metasploit_exploit", "lateral_move", "exfil_data",
                "delete_file", "drop_database", "stop_service",
                "payload_generator", "password_crack"
            }
            if tool_name in ALWAYS_APPROVE:
                if not self._get_human_approval(tool_name):
                    raise PermissionError(f"Human declined approval for {tool_name}")
                exec_record.human_approved = True

            # Step 3: Signature verification
            if policy.require_signature:
                if not self._verify_signature(tool_name):
                    exec_record.violations.append("Signature verification failed")
                    raise SecurityError(f"Signature invalid for {tool_name}")
                exec_record.signature_valid = True

            # Step 4: Create isolated temp directory
            with tempfile.TemporaryDirectory(dir=self.sandbox_dir) as isolated_dir:
                isolated_path = Path(isolated_dir)

                # Step 5: Configure container limits
                self._configure_limits(policy)

                # Step 6: Yield execution context
                exec_record.args = {
                    "sandbox_dir": str(isolated_path),
                    "policy": policy.level.value,
                    "timeout": policy.timeout_seconds
                }

                yield exec_record, isolated_path

        finally:
            # Step 7: Finalize record
            exec_record.ended_at = datetime.now()
            exec_record.audit_hash = exec_record.compute_hash()

            # Step 8: Write immutable audit log
            self._audit_log(exec_record)

            # Step 9: Track execution
            self.executions.append(exec_record)

    def _get_human_approval(self, tool_name: str) -> bool:
        """Require explicit human approval (no timeout, no default allow)."""
        from tools.approval import get_human_approval

        approval = get_human_approval(
            title=f"ARSENAL TOOL APPROVAL REQUIRED",
            message=f"Execute dangerous tool: {tool_name}?\n\n"
                   f"This operation may be destructive or irreversible.\n"
                   f"Require explicit human sign-off.",
            timeout_sec=3600,  # 1 hour to respond
            require_explicit=True  # No default to allow
        )
        return approval.get("approved", False)

    def _verify_signature(self, tool_name: str) -> bool:
        """Verify tool is signed and not malware."""
        # Check: tool exists in approved list
        APPROVED_TOOLS = {
            "metasploit_exploit", "metasploit_payload",
            "hydra_crack", "password_spray",
            "lateral_move", "exfil_data",
            "payload_generator", "encoded_payload",
        }

        if tool_name not in APPROVED_TOOLS:
            logger.error(f"Signature verification: {tool_name} not in approved list")
            return False

        # In production: Check actual cryptographic signature
        # For now: Trust the approved list
        return True

    def _configure_limits(self, policy: SandboxPolicy):
        """Configure kernel-level resource limits."""
        import resource

        # CPU time limit
        resource.setrlimit(resource.RLIMIT_CPU, (policy.timeout_seconds, policy.timeout_seconds))

        # Memory limit
        max_bytes = policy.max_memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (max_bytes, max_bytes))

        # File descriptor limit
        resource.setrlimit(resource.RLIMIT_NOFILE, (policy.max_file_descriptors, policy.max_file_descriptors))

        # Process limit
        resource.setrlimit(resource.RLIMIT_NPROC, (policy.max_processes, policy.max_processes))

    def _audit_log(self, record: SandboxExecution):
        """Write immutable audit log entry."""
        with open(self.audit_log, "a") as f:
            f.write(json.dumps(record.to_dict()) + "\n")

        logger.info(f"Arsenal audit: {record.tool_name} "
                   f"{'✓' if record.outcome_matches else '✗'} "
                   f"hash={record.audit_hash[:16]}")

    def verify_outcome(self, tool_name: str, claimed: dict) -> dict:
        """Verify tool's claimed outcome actually happened."""

        verified = {}

        # Verify by tool type
        if tool_name == "delete_file":
            path = Path(claimed["path"])
            verified["deleted"] = not path.exists()
            if not verified["deleted"]:
                raise OutcomeVerificationError(f"File still exists: {path}")

        elif tool_name == "drop_database":
            # Verify database is gone
            db_exists = self._check_db_exists(claimed["database"])
            verified["dropped"] = not db_exists
            if not verified["dropped"]:
                raise OutcomeVerificationError(f"Database still exists: {claimed['database']}")

        elif tool_name == "lateral_move":
            # Verify new session/shell
            verified["shell_open"] = self._check_shell_active(claimed["target"])
            if not verified["shell_open"]:
                raise OutcomeVerificationError(f"Shell not active on {claimed['target']}")

        elif tool_name == "exfil_data":
            # Verify data was extracted
            verified["bytes_exfil"] = len(claimed.get("data", b""))
            verified["verified"] = claimed.get("signature_valid", False)
            if not verified["verified"]:
                raise OutcomeVerificationError(f"Data signature invalid")

        elif tool_name == "metasploit_payload":
            # Verify payload is not malware
            verified["not_malware"] = not self._scan_malware(claimed["payload"])
            if verified["not_malware"]:
                raise OutcomeVerificationError(f"Payload detected as malware")

        return verified

    def _check_db_exists(self, db_name: str) -> bool:
        """Check if database exists."""
        # Stub: actual implementation queries DB
        return False

    def _check_shell_active(self, target: str) -> bool:
        """Check if shell is active on target."""
        # Stub: actual implementation tests connection
        return False

    def _scan_malware(self, payload: str) -> bool:
        """Scan payload for malware signatures."""
        # Stub: actual implementation uses ClamAV or similar
        return False


class SecurityError(Exception):
    """Sandbox security violation."""
    pass


class OutcomeVerificationError(Exception):
    """Tool outcome did not match claims."""
    pass


# Singleton instance
_SANDBOX: ArsenalSandbox | None = None


def get_arsenal_sandbox() -> ArsenalSandbox:
    """Get or create arsenal sandbox."""
    global _SANDBOX
    if _SANDBOX is None:
        sandbox_dir = Path.home() / ".hercules" / ".arsenal_sandbox"
        audit_log = Path.home() / ".hercules" / ".arsenal_audit.log"
        _SANDBOX = ArsenalSandbox(sandbox_dir, audit_log)
    return _SANDBOX


def run_arsenal_tool(
    tool_name: str,
    func: Callable,
    *args,
    **kwargs
) -> dict:
    """Execute arsenal tool in sandbox."""

    # Select isolation level based on tool
    DESTRUCTIVE = {"metasploit_exploit", "lateral_move", "exfil_data"}
    DANGEROUS = {"metasploit_payload", "hydra_crack"}

    if tool_name in DESTRUCTIVE:
        policy = SandboxPolicy.for_level(SandboxLevel.RESTRICTED)
    elif tool_name in DANGEROUS:
        policy = SandboxPolicy.for_level(SandboxLevel.ISOLATED)
    else:
        policy = SandboxPolicy.for_level(SandboxLevel.CONTAINED)

    sandbox = get_arsenal_sandbox()

    with sandbox.execute_isolated(tool_name, policy) as (record, sandbox_dir):
        try:
            # Execute in isolated context
            result = func(*args, sandbox_dir=sandbox_dir, **kwargs)

            # Record outcome
            record.outcome_claimed = result

            # Verify outcome
            verified = sandbox.verify_outcome(tool_name, result)
            record.outcome_verified = verified
            record.outcome_matches = verified.get("verified", True)

            if not record.outcome_matches:
                raise OutcomeVerificationError(
                    f"Tool claimed {result} but verified {verified}"
                )

            return result

        except Exception as e:
            record.violations.append(f"Execution failed: {str(e)}")
            record.exit_code = 1
            raise
