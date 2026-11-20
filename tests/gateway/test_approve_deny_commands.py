"""Tests for /approve and /deny gateway commands.

Verifies that dangerous command approvals use the blocking gateway approval
mechanism — the agent thread blocks until the user responds with /approve
or /deny, mirroring the CLI's synchronous input() flow.

Supports multiple concurrent approvals (parallel subagents, execute_code)
via a per-session queue.
"""

import os
import threading
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.platforms.base import MessageEvent
from gateway.session import SessionSource


def _make_source() -> SessionSource:
    return SessionSource(
        platform=Platform.TELEGRAM,
        user_id="u1",
        chat_id="c1",
        user_name="tester",
        chat_type="dm",
    )


def _make_event(text: str) -> MessageEvent:
    return MessageEvent(
        text=text,
        source=_make_source(),
        message_id="m1",
    )


def _make_runner():
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        platforms={Platform.TELEGRAM: PlatformConfig(enabled=True, token="***")}
    )
    adapter = MagicMock()
    adapter.send = AsyncMock()
    runner.adapters = {Platform.TELEGRAM: adapter}
    runner._voice_mode = {}
    runner.hooks = SimpleNamespace(emit=AsyncMock(), loaded_hooks=False)
    runner.session_store = MagicMock()
    runner._running_agents = {}
    runner._pending_messages = {}
    runner._pending_approvals = {}
    runner._background_tasks = set()
    runner._session_db = None
    runner._reasoning_config = None
    runner._provider_routing = {}
    runner._fallback_model = None
    runner._show_reasoning = False
    runner._is_user_authorized = lambda _source: True
    runner._set_session_env = lambda _context: None
    return runner


def _clear_approval_state():
    """Reset all module-level approval state between tests."""
    from tools import approval as mod

    mod._gateway_queues.clear()
    mod._gateway_notify_cbs.clear()
    mod._session_approved.clear()
    mod._permanent_approved.clear()
    mod._pending.clear()


# ------------------------------------------------------------------
# Blocking gateway approval infrastructure (tools/approval.py)
# ------------------------------------------------------------------


class TestBlockingGatewayApproval:
    """Tests for the blocking approval mechanism in tools/approval.py."""

    def setup_method(self):
        _clear_approval_state()

    def test_register_and_resolve_unblocks_entry(self):
        """resolve_gateway_approval signals the entry's event."""
        from tools.approval import (
            register_gateway_notify,
            unregister_gateway_notify,
            resolve_gateway_approval,
            has_blocking_approval,
            _ApprovalEntry,
            _gateway_queues,
        )

        session_key = "test-session"
        register_gateway_notify(session_key, lambda d: None)

        # Simulate what check_all_command_guards does
        entry = _ApprovalEntry({"command": "rm -rf /"})
        _gateway_queues.setdefault(session_key, []).append(entry)

        assert has_blocking_approval(session_key) is True

        # Resolve from another thread
        def resolve():
            time.sleep(0.1)
            resolve_gateway_approval(session_key, "once")

        t = threading.Thread(target=resolve)
        t.start()
        resolved = entry.event.wait(timeout=5)
        t.join()

        assert resolved is True
        assert entry.result == "once"
        unregister_gateway_notify(session_key)

    def test_resolve_returns_zero_when_no_pending(self):
        from tools.approval import resolve_gateway_approval

        assert resolve_gateway_approval("nonexistent", "once") == 0

    def test_resolve_all_unblocks_multiple_entries(self):
        """resolve_gateway_approval with resolve_all=True signals all entries."""
        from tools.approval import (
            resolve_gateway_approval,
            _ApprovalEntry,
            _gateway_queues,
        )

        session_key = "test-all"
        e1 = _ApprovalEntry({"command": "cmd1"})
        e2 = _ApprovalEntry({"command": "cmd2"})
        e3 = _ApprovalEntry({"command": "cmd3"})
        _gateway_queues[session_key] = [e1, e2, e3]

        count = resolve_gateway_approval(session_key, "session", resolve_all=True)
        assert count == 3
        assert all(e.event.is_set() for e in [e1, e2, e3])
        assert all(e.result == "session" for e in [e1, e2, e3])

    def test_resolve_single_pops_oldest_fifo(self):
        """resolve_gateway_approval without resolve_all resolves oldest first."""
        from tools.approval import (
            resolve_gateway_approval,
            _ApprovalEntry,
            _gateway_queues,
        )

        session_key = "test-fifo"
        e1 = _ApprovalEntry({"command": "first"})
        e2 = _ApprovalEntry({"command": "second"})
        _gateway_queues[session_key] = [e1, e2]

        count = resolve_gateway_approval(session_key, "once")
        assert count == 1
        assert e1.event.is_set()
        assert e1.result == "once"
        assert not e2.event.is_set()
        assert len(_gateway_queues[session_key]) == 1

    def test_unregister_signals_all_entries(self):
        """unregister_gateway_notify signals all waiting entries to prevent hangs."""
        from tools.approval import (
            register_gateway_notify,
            unregister_gateway_notify,
            _ApprovalEntry,
            _gateway_queues,
        )

        session_key = "test-cleanup"
        register_gateway_notify(session_key, lambda d: None)

        e1 = _ApprovalEntry({"command": "cmd1"})
        e2 = _ApprovalEntry({"command": "cmd2"})
        _gateway_queues[session_key] = [e1, e2]

        unregister_gateway_notify(session_key)
        assert e1.event.is_set()
        assert e2.event.is_set()

    def test_clear_session_denies_and_signals_all_entries(self):
        """clear_session must wake blocked entries during boundary cleanup."""
        from tools.approval import clear_session, _ApprovalEntry, _gateway_queues

        session_key = "test-boundary-cleanup"
        e1 = _ApprovalEntry({"command": "cmd1"})
        e2 = _ApprovalEntry({"command": "cmd2"})
        _gateway_queues[session_key] = [e1, e2]

        clear_session(session_key)

        assert e1.event.is_set()
        assert e2.event.is_set()
        assert e1.result == "deny"
        assert e2.result == "deny"
        assert session_key not in _gateway_queues


# ------------------------------------------------------------------
# /approve command
# ------------------------------------------------------------------




# ------------------------------------------------------------------
# /deny command
# ------------------------------------------------------------------




# ------------------------------------------------------------------
# Bare "yes" must NOT trigger approval
# ------------------------------------------------------------------




# ------------------------------------------------------------------
# End-to-end blocking flow
# ------------------------------------------------------------------




# ------------------------------------------------------------------
# Fallback: no gateway callback (cron/batch mode)
# ------------------------------------------------------------------




# ------------------------------------------------------------------
# Regression: cross-session approval routing isolation (#24100)
# ------------------------------------------------------------------


