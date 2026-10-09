"""terminal(background=true, heartbeat=N): periodic "still running" events that
carry only the output produced since the previous heartbeat."""

import queue
import time

import pytest

import tools.process_registry as pr
from tools.process_registry import (
    ProcessRegistry,
    ProcessSession,
    format_process_notification,
)


@pytest.fixture
def fast_heartbeat(monkeypatch):
    monkeypatch.setattr(pr, "HEARTBEAT_MIN_SECONDS", 1)
    monkeypatch.setattr(pr, "HEARTBEAT_TICK_SECONDS", 0.1)


def _events(registry, kind, timeout):
    out, deadline = [], time.time() + timeout
    while time.time() < deadline:
        try:
            evt = registry.completion_queue.get(timeout=0.1)
        except queue.Empty:
            continue
        if evt.get("type") == kind:
            out.append(evt)
    return out


def test_arm_heartbeat_enforces_floor():
    registry = ProcessRegistry()
    session = ProcessSession(id="proc_x", command="true")
    assert registry.arm_heartbeat(session, 5) == pr.HEARTBEAT_MIN_SECONDS
    assert registry.arm_heartbeat(session, 600) == 600


def test_heartbeat_carries_only_new_output(fast_heartbeat):
    registry = ProcessRegistry()
    session = registry.spawn_local(
        "for i in 1 2 3 4; do echo tick$i; sleep 0.6; done", cwd="/tmp"
    )
    registry.arm_heartbeat(session, 1)
    beats = _events(registry, "heartbeat", 3.5)
    assert len(beats) >= 2
    assert [b["seq"] for b in beats] == list(range(1, len(beats) + 1))
    combined = "".join(b["output"] for b in beats)
    # Every tick seen so far appears once across heartbeats (no repeated slices).
    for tick in ("tick1", "tick2"):
        assert combined.count(tick) == 1
    assert all(b["session_id"] == session.id for b in beats)


def test_no_heartbeat_after_exit(fast_heartbeat):
    registry = ProcessRegistry()
    session = registry.spawn_local("echo done", cwd="/tmp")
    registry.arm_heartbeat(session, 1)
    deadline = time.time() + 5
    while not session.exited and time.time() < deadline:
        time.sleep(0.05)
    assert session.exited
    assert _events(registry, "heartbeat", 1.5) == []


def test_heartbeat_formats_as_still_running_not_as_exit():
    text = format_process_notification({
        "type": "heartbeat",
        "session_id": "proc_1",
        "command": "pytest",
        "seq": 2,
        "interval": 60,
        "elapsed": 125,
        "output": "",
    })
    assert "heartbeat #2" in text
    assert "still running after 125s" in text
    assert "no new output" in text
    assert "exit code" not in text


def test_gateway_and_tui_route_heartbeats():
    from gateway.run import (
        _drain_gateway_watch_events,
        _format_gateway_process_notification,
    )
    from tui_gateway.server import _notification_event_dedup_key

    q = queue.Queue()
    evt = {"type": "heartbeat", "session_id": "proc_1", "command": "c", "seq": 1}
    q.put(evt)
    assert _drain_gateway_watch_events(q) == [evt]
    assert "heartbeat #1" in _format_gateway_process_notification(evt)
    second = dict(evt, seq=2)
    assert _notification_event_dedup_key(evt) != _notification_event_dedup_key(second)


def test_terminal_schema_and_validation():
    import json

    from tools.terminal_tool import TERMINAL_SCHEMA, terminal_tool

    hb = TERMINAL_SCHEMA["parameters"]["properties"]["heartbeat"]
    assert hb["type"] == "integer" and hb["minimum"] == 60
    for bad in (-5, "60", True, 1.5):
        out = json.loads(terminal_tool(command="true", background=True, heartbeat=bad))
        assert "heartbeat must be a whole number" in out["error"]
