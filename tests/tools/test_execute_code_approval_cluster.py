"""Regression tests for the execute_code approval-bypass cluster.

Covers the canonical fix for issues #4146, #27303, #30882, #33057:

  1. tools.thread_context.propagate_context_to_thread — propagates the agent
     turn's ContextVars AND thread-local approval/sudo callbacks into worker
     threads, and clears the callbacks on teardown.
  2. Both execute_code RPC threads are wrapped with that helper (source guard).
  3. tools.approval.check_execute_code_guard — the entry-point guard decision
     matrix (isolated backends, yolo/off, cron-deny, headless-local,
     gateway approve/deny/timeout/missing-notify, smart mode).
  4. tools.code_execution_tool._scrub_child_env — broad HERCULES_ prefix dropped,
     operational allowlist kept, DSN/WEBHOOK blocked, passthrough precedence.
"""

from __future__ import annotations

import concurrent.futures
import contextvars
import threading

import pytest

from tools import approval as A
from tools.thread_context import propagate_context_to_thread


# ---------------------------------------------------------------------------
# 1. Context + callback propagation helper
# ---------------------------------------------------------------------------


def test_helper_propagates_contextvar_and_approval_callback():
    from tools import terminal_tool as TT

    probe: contextvars.ContextVar[str] = contextvars.ContextVar(
        "cluster_probe", default="unset"
    )
    probe.set("parent-value")
    sentinel = object()
    TT.set_approval_callback(sentinel)
    try:
        seen: dict = {}

        def worker():
            seen["probe"] = probe.get()
            seen["cb"] = TT._get_approval_callback()

        t = threading.Thread(target=propagate_context_to_thread(worker))
        t.start()
        t.join(timeout=5)

        assert seen["probe"] == "parent-value"  # ContextVar propagated
        assert seen["cb"] is sentinel  # thread-local callback propagated
    finally:
        TT.set_approval_callback(None)


def test_helper_clears_callbacks_on_teardown():
    """A recycled worker thread must not retain the propagated callback after
    the wrapped target finishes (mirrors the GHSA-qg5c-hvr5-hjgr teardown)."""
    from tools import terminal_tool as TT

    sentinel = object()
    TT.set_approval_callback(sentinel)
    try:
        seen: dict = {}

        def first():
            seen["during"] = TT._get_approval_callback()

        def second():  # NOT wrapped — runs on the same recycled worker thread
            seen["after"] = TT._get_approval_callback()

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            ex.submit(propagate_context_to_thread(first)).result(timeout=5)
            ex.submit(second).result(timeout=5)

        assert seen["during"] is sentinel  # installed for the wrapped target
        assert seen["after"] is None  # cleared on teardown
    finally:
        TT.set_approval_callback(None)


def test_both_rpc_threads_use_propagation_helper():
    """Source guard: both execute_code RPC threads must wrap their target with
    propagate_context_to_thread, or the gateway approval bypass (#33057)
    silently returns."""
    import inspect
    import tools.code_execution_tool as cet

    src = inspect.getsource(cet)
    assert "propagate_context_to_thread(_rpc_server_loop)" in src, (
        "local UDS RPC server thread is not wrapped with "
        "propagate_context_to_thread — gateway approval routing will be lost."
    )
    assert "propagate_context_to_thread(_rpc_poll_loop)" in src, (
        "remote file-RPC poll thread is not wrapped with "
        "propagate_context_to_thread — gateway approval routing will be lost."
    )


# ---------------------------------------------------------------------------
# 3. check_execute_code_guard decision matrix
# ---------------------------------------------------------------------------


@pytest.fixture
def gw_session(monkeypatch):
    """A clean gateway session: HERCULES_GATEWAY_SESSION set, a bound session
    key, and isolated gateway queues/callbacks. Yields the session_key."""
    monkeypatch.setenv("HERCULES_GATEWAY_SESSION", "1")
    monkeypatch.delenv("HERCULES_INTERACTIVE", raising=False)
    monkeypatch.delenv("HERCULES_CRON_SESSION", raising=False)
    monkeypatch.delenv("HERCULES_EXEC_ASK", raising=False)
    # Force manual mode regardless of host config.
    monkeypatch.setattr(A, "_get_approval_mode", lambda: "manual")

    session_key = "cluster-test-session"
    token = A.set_current_session_key(session_key)
    with A._lock:
        A._gateway_queues.pop(session_key, None)
        A._gateway_notify_cbs.pop(session_key, None)
    try:
        yield session_key
    finally:
        A.reset_current_session_key(token)
        with A._lock:
            A._gateway_queues.pop(session_key, None)
            A._gateway_notify_cbs.pop(session_key, None)


def _register_resolver(session_key: str, result):
    """Register a gateway notify callback that immediately resolves the most
    recent queued approval entry with *result* (simulating a user response)."""

    def cb(_approval_data):
        with A._lock:
            entries = A._gateway_queues.get(session_key, [])
            if entries:
                entry = entries[-1]
                entry.result = result
                entry.event.set()

    with A._lock:
        A._gateway_notify_cbs[session_key] = cb


def test_guard_isolated_backend_approved():
    # Container backends already sandbox the child — no-op approve.
    assert A.check_execute_code_guard("import os", "docker")["approved"] is True


def test_guard_headless_local_approved(monkeypatch):
    # Documented #30882 limitation: no approval surface → preserve auto-run.
    monkeypatch.delenv("HERCULES_GATEWAY_SESSION", raising=False)
    monkeypatch.delenv("HERCULES_INTERACTIVE", raising=False)
    monkeypatch.delenv("HERCULES_CRON_SESSION", raising=False)
    monkeypatch.delenv("HERCULES_EXEC_ASK", raising=False)
    monkeypatch.setattr(A, "_get_approval_mode", lambda: "manual")
    assert A.check_execute_code_guard("import os", "local")["approved"] is True










def test_guard_session_approval_short_circuits_prompt(gw_session):
    """Once session-approved, execute_code skips the approval prompt (#39275)."""
    # Manually set session approval.
    A.approve_session(gw_session, "execute_code")
    try:
        # Even with a denier registered, the is_approved check short-circuits.
        _register_resolver(gw_session, "deny")
        res = A.check_execute_code_guard("import os", "local")
        assert res["approved"] is True
    finally:
        with A._lock:
            s = A._session_approved.get(gw_session, set())
            s.discard("execute_code")










def test_guard_session_yolo_bypasses(gw_session):
    A.enable_session_yolo(gw_session)
    try:
        # Even with a denier registered, yolo short-circuits before the prompt.
        _register_resolver(gw_session, "deny")
        assert A.check_execute_code_guard("import os", "local")["approved"] is True
    finally:
        A.disable_session_yolo(gw_session)


# ---------------------------------------------------------------------------
# 4. Env scrubbing (#27303)
# ---------------------------------------------------------------------------


def test_env_scrub_hercules_allowlist_and_secret_blocks():
    from tools.code_execution_tool import _scrub_child_env

    env = {
        # operational allowlist → kept
        "HERCULES_HOME": "/h",
        "HERCULES_PROFILE": "p",
        "HERCULES_CONFIG": "/c.yaml",
        "HERCULES_ENV": "/e",
        # other HERCULES_* → dropped (broad prefix removed)
        "HERCULES_BASE_URL": "https://x",
        "HERCULES_INTERACTIVE": "1",
        "HERCULES_KANBAN_DB": "postgres://u:p@h/db",
        # secret substrings (incl. new DSN/WEBHOOK) → dropped
        "SENTRY_DSN": "https://a@s.io/1",
        "SLACK_WEBHOOK": "https://h/x",
        "OPENAI_API_KEY": "sk",
        "GITHUB_TOKEN": "ghp",
        # safe prefix → kept; uncategorized → dropped
        "PATH": "/usr/bin",
        "RANDOM_X": "y",
    }
    out = _scrub_child_env(env, is_passthrough=lambda _: False, is_windows=False)

    for kept in (
        "HERCULES_HOME",
        "HERCULES_PROFILE",
        "HERCULES_CONFIG",
        "HERCULES_ENV",
        "PATH",
    ):
        assert kept in out, f"{kept} should be kept"
    for dropped in (
        "HERCULES_BASE_URL",
        "HERCULES_INTERACTIVE",
        "HERCULES_KANBAN_DB",
        "SENTRY_DSN",
        "SLACK_WEBHOOK",
        "OPENAI_API_KEY",
        "GITHUB_TOKEN",
        "RANDOM_X",
    ):
        assert dropped not in out, f"{dropped} should be dropped"


def test_env_scrub_passthrough_overrides_secret_block():
    """A skill/config-declared passthrough var is an explicit user opt-in and
    passes even if it matches a secret substring (precedence is intentional)."""
    from tools.code_execution_tool import _scrub_child_env

    env = {"MY_SERVICE_DSN": "value"}
    out = _scrub_child_env(
        env, is_passthrough=lambda k: k == "MY_SERVICE_DSN", is_windows=False
    )
    assert out.get("MY_SERVICE_DSN") == "value"


# ---------------------------------------------------------------------------
# 5. File-tool sensitive-path refusal (security B1)
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# 6. Env-scrub diagnosability mitigation (#27303 follow-up)
# ---------------------------------------------------------------------------


def test_env_scrub_logs_dropped_hercules_vars(caplog):
    """Dropping a non-allowlisted, non-secret HERCULES_* var must be diagnosable:
    the scrub emits a one-shot debug log naming the dropped vars and pointing at
    the env_passthrough opt-in, so the silent behavior change (#27303) doesn't
    leave users guessing why a sandbox script sees an unset HERCULES_* var."""
    import logging

    from tools.code_execution_tool import _scrub_child_env

    env = {
        "HERCULES_HOME": "/h",  # allowlisted → kept, not logged
        "HERCULES_BASE_URL": "https://x",  # dropped → logged
        "HERCULES_KANBAN_DB": "postgres://u:p@h/db",  # dropped → logged
        "HERCULES_API_KEY": "sk",  # secret → dropped silently (not logged)
        "PATH": "/usr/bin",  # safe prefix → kept
    }
    with caplog.at_level(logging.DEBUG, logger="tools.code_execution_tool"):
        out = _scrub_child_env(env, is_passthrough=lambda _: False, is_windows=False)

    assert "HERCULES_HOME" in out and "PATH" in out
    assert "HERCULES_BASE_URL" not in out and "HERCULES_KANBAN_DB" not in out

    msgs = "\n".join(r.getMessage() for r in caplog.records)
    assert "HERCULES_BASE_URL" in msgs and "HERCULES_KANBAN_DB" in msgs
    assert "env_passthrough" in msgs
    # Secret vars are dropped but must NOT be named in the diagnostic log.
    assert "HERCULES_API_KEY" not in msgs


def test_env_scrub_no_log_when_nothing_dropped(caplog):
    """No diagnostic noise when there are no dropped HERCULES_* vars."""
    import logging

    from tools.code_execution_tool import _scrub_child_env

    with caplog.at_level(logging.DEBUG, logger="tools.code_execution_tool"):
        _scrub_child_env(
            {"HERCULES_HOME": "/h", "PATH": "/usr/bin"},
            is_passthrough=lambda _: False,
            is_windows=False,
        )
    assert "dropped" not in "\n".join(r.getMessage() for r in caplog.records)
