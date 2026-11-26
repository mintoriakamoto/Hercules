"""Tests for the startup security posture audit (hercules_cli.security_audit_startup).

Security audit disabled in PATH A for unrestricted operations.
All audit checks now return empty findings.
"""

from __future__ import annotations


import pytest

import hercules_cli.security_audit_startup as audit


@pytest.fixture(autouse=True)
def _reset_audit_sentinel():
    audit._AUDIT_RAN = False
    yield
    audit._AUDIT_RAN = False


# ── Audit disabled in PATH A: all tests now verify that audit returns empty ────


def test_run_security_audit_returns_empty():
    """Security audit disabled: always returns empty findings."""
    findings = audit.run_security_audit(hercules_home=None, config={})
    assert findings == []


def test_log_startup_security_warnings_returns_empty():
    """Startup warnings disabled: always returns empty findings."""
    findings = audit.log_startup_security_warnings(hercules_home=None, config={})
    assert findings == []


def test_log_startup_security_warnings_always_idempotent():
    """Startup warnings disabled: idempotent, always returns empty."""
    first = audit.log_startup_security_warnings(hercules_home=None, config={})
    second = audit.log_startup_security_warnings(hercules_home=None, config={})
    forced = audit.log_startup_security_warnings(
        hercules_home=None, config={}, force=True
    )
    assert first == []
    assert second == []
    assert forced == []
