"""Tests for arsenal sandbox.

Philosophy: ZERO TRUST
- Default: DENY everything
- Test: Verify restrictions are enforced
- Exception: Only approve after verification
"""

import pytest
from pathlib import Path
from datetime import datetime
import tempfile

from tools.arsenal_sandbox import (
    ArsenalSandbox,
    SandboxPolicy,
    SandboxLevel,
    SandboxExecution,
    SecurityError,
    OutcomeVerificationError,
)


class TestSandboxPolicy:
    """Test sandbox policy creation."""

    def test_restricted_policy(self):
        """Restricted level has NO network, NO filesystem."""
        policy = SandboxPolicy.for_level(SandboxLevel.RESTRICTED)

        assert policy.deny_all_network is True
        assert len(policy.allowed_ips) == 0
        assert len(policy.allowed_ports) == 0
        assert policy.deny_all_filesystem is True
        assert len(policy.allowed_read_dirs) == 0
        assert len(policy.allowed_write_dirs) == 0
        assert policy.timeout_seconds == 30
        assert policy.max_memory_mb == 512

    def test_isolated_policy(self):
        """Isolated level: localhost only."""
        policy = SandboxPolicy.for_level(SandboxLevel.ISOLATED)

        assert policy.allowed_ips == ["127.0.0.1"]
        assert policy.deny_all_network is True
        assert policy.timeout_seconds == 120
        assert policy.max_memory_mb == 1024

    def test_contained_policy(self):
        """Contained level: private network only."""
        policy = SandboxPolicy.for_level(SandboxLevel.CONTAINED)

        assert "10.0.0.0/8" in policy.allowed_ips
        assert "192.168.0.0/16" in policy.allowed_ips
        assert 22 in policy.allowed_ports  # SSH
        assert 443 in policy.allowed_ports  # HTTPS
        assert policy.timeout_seconds == 300
        assert policy.max_memory_mb == 2048


class TestRateLimit:
    """Test rate limiting."""

    def test_rate_limit_hourly(self):
        """Max 5 calls per hour."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox = ArsenalSandbox(Path(tmpdir), Path(tmpdir) / "audit.log")

            # First 5 should succeed
            for i in range(5):
                assert sandbox.check_rate_limit("test_tool") is True

            # 6th should fail
            assert sandbox.check_rate_limit("test_tool") is False

    def test_rate_limit_60s_destructive(self):
        """Destructive tools: max 1 per 60s."""
        import time
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox = ArsenalSandbox(Path(tmpdir), Path(tmpdir) / "audit.log")

            # First call succeeds
            assert sandbox.check_rate_limit("metasploit_exploit") is True

            # Second call within 60s fails
            assert sandbox.check_rate_limit("metasploit_exploit") is False

            # After 61s, succeeds again
            sandbox.call_times["metasploit_exploit"][0] -= 61
            assert sandbox.check_rate_limit("metasploit_exploit") is True


class TestAuditLog:
    """Test immutable audit logging."""

    def test_audit_log_written(self):
        """Every execution is logged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            sandbox = ArsenalSandbox(tmppath, tmppath / "audit.log")

            exec_record = SandboxExecution(
                tool_name="test_tool",
                args={"target": "10.0.0.1"},
                started_at=datetime.now()
            )
            exec_record.ended_at = datetime.now()
            exec_record.outcome_matches = True

            sandbox._audit_log(exec_record)

            # Verify log file exists and contains entry
            assert (tmppath / "audit.log").exists()
            log_content = (tmppath / "audit.log").read_text()
            assert "test_tool" in log_content
            assert "10.0.0.1" in log_content

    def test_audit_hash_immutable(self):
        """Hash changes if record changes."""
        exec1 = SandboxExecution(
            tool_name="test",
            args={"x": 1},
            started_at=datetime.now(),
            ended_at=datetime.now()
        )
        hash1 = exec1.compute_hash()

        exec2 = SandboxExecution(
            tool_name="test",
            args={"x": 2},  # Different
            started_at=datetime.now(),
            ended_at=datetime.now()
        )
        hash2 = exec2.compute_hash()

        assert hash1 != hash2


class TestSecurityEnforcement:
    """Test that security is enforced."""

    def test_signature_required(self):
        """Signature verification is mandatory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox = ArsenalSandbox(Path(tmpdir), Path(tmpdir) / "audit.log")

            # Unknown tool should fail signature check
            assert sandbox._verify_signature("unknown_malicious_tool") is False

    def test_approved_tools_only(self):
        """Only approved tools can run."""
        from tools.arsenal_tools_sandboxed import _APPROVED_PAYLOADS

        # These should be approved
        assert "windows/meterpreter/reverse_tcp" in _APPROVED_PAYLOADS

        # Random payload should not be approved
        with pytest.raises(ValueError, match="not approved"):
            from tools.arsenal_tools_sandboxed import metasploit_payload
            metasploit_payload(payload_type="custom/malware/custom")

    def test_private_network_only(self):
        """Only private IPs allowed for exploits."""
        from tools.arsenal_tools_sandboxed import metasploit_exploit, _is_private_ip

        # Private IPs
        assert _is_private_ip("10.0.0.1") is True
        assert _is_private_ip("192.168.1.1") is True
        assert _is_private_ip("172.16.0.1") is True

        # Public IPs
        assert _is_private_ip("8.8.8.8") is False
        assert _is_private_ip("1.1.1.1") is False

        # Public IP should fail
        with pytest.raises(ValueError, match="private network"):
            metasploit_exploit(target="8.8.8.8", exploit="windows/smb/ms17-010", payload="windows/meterpreter/reverse_tcp")


class TestOutcomeVerification:
    """Test that outcomes are verified."""

    def test_deletion_verified(self):
        """File deletion is verified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            test_file = tmppath / "test.txt"
            test_file.write_text("test")

            sandbox = ArsenalSandbox(tmppath, tmppath / "audit.log")

            # Verify file exists
            claimed = {"path": str(test_file)}

            # Before deletion
            with pytest.raises(OutcomeVerificationError):
                sandbox.verify_outcome("delete_file", claimed)

            # After deletion
            test_file.unlink()
            verified = sandbox.verify_outcome("delete_file", claimed)
            assert verified["deleted"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
