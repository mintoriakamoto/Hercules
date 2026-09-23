"""Tests for the cross-turn stagnation guard pure helpers.

These cover the fingerprinting, config gate, threshold normalization, and the
nudge/halt message builders. The loop wiring that consumes them lives in
``agent/conversation_loop.py`` and is exercised by the loop's own suite; here we
pin the deterministic building blocks the guard's correctness rests on.
"""

import os
from types import SimpleNamespace

import pytest

from agent.stagnation_guard import (
    build_stagnation_halt_message,
    build_stagnation_nudge,
    stagnation_guard_enabled,
    stagnation_limits,
    tool_calls_fingerprint,
)


def _tc(name, arguments):
    """Build an OpenAI-style tool call object (attribute access)."""
    return SimpleNamespace(function=SimpleNamespace(name=name, arguments=arguments))


class TestFingerprint:
    def test_empty_list_is_empty_fingerprint(self):
        assert tool_calls_fingerprint([]) == ""
        assert tool_calls_fingerprint(None) == ""

    def test_same_calls_same_fingerprint(self):
        a = [_tc("read_file", '{"path": "foo.py"}')]
        b = [_tc("read_file", '{"path": "foo.py"}')]
        assert tool_calls_fingerprint(a) == tool_calls_fingerprint(b)
        assert tool_calls_fingerprint(a) != ""

    def test_different_arguments_differ(self):
        a = [_tc("read_file", '{"path": "foo.py"}')]
        b = [_tc("read_file", '{"path": "bar.py"}')]
        assert tool_calls_fingerprint(a) != tool_calls_fingerprint(b)

    def test_different_tool_differs(self):
        a = [_tc("read_file", '{"path": "foo.py"}')]
        b = [_tc("write_file", '{"path": "foo.py"}')]
        assert tool_calls_fingerprint(a) != tool_calls_fingerprint(b)

    def test_order_independent(self):
        a = [_tc("read_file", "{}"), _tc("grep", '{"q": "x"}')]
        b = [_tc("grep", '{"q": "x"}'), _tc("read_file", "{}")]
        assert tool_calls_fingerprint(a) == tool_calls_fingerprint(b)

    def test_dict_shaped_tool_calls(self):
        a = [{"function": {"name": "read_file", "arguments": '{"path": "foo.py"}'}}]
        b = [_tc("read_file", '{"path": "foo.py"}')]
        assert tool_calls_fingerprint(a) == tool_calls_fingerprint(b)

    def test_none_fields_do_not_crash(self):
        a = [_tc(None, None)]
        # Fingerprint is stable and non-empty (a call with empty name/args is
        # still a call), and matches an explicit empty-string pair.
        b = [_tc("", "")]
        assert tool_calls_fingerprint(a) == tool_calls_fingerprint(b)
        assert tool_calls_fingerprint(a) != ""


class TestEnabled:
    def test_default_on(self, monkeypatch):
        monkeypatch.delenv("HERCULES_STAGNATION_GUARD", raising=False)
        assert stagnation_guard_enabled({}) is True

    def test_env_off_wins(self, monkeypatch):
        monkeypatch.setenv("HERCULES_STAGNATION_GUARD", "off")
        assert stagnation_guard_enabled({"agent": {"stagnation_guard": True}}) is False

    def test_env_on_wins(self, monkeypatch):
        monkeypatch.setenv("HERCULES_STAGNATION_GUARD", "1")
        assert stagnation_guard_enabled({"agent": {"stagnation_guard": False}}) is True

    def test_config_bool(self, monkeypatch):
        monkeypatch.delenv("HERCULES_STAGNATION_GUARD", raising=False)
        assert stagnation_guard_enabled({"agent": {"stagnation_guard": False}}) is False

    def test_config_string(self, monkeypatch):
        monkeypatch.delenv("HERCULES_STAGNATION_GUARD", raising=False)
        assert stagnation_guard_enabled({"agent": {"stagnation_guard": "no"}}) is False


class TestLimits:
    def test_defaults(self, monkeypatch):
        for var in (
            "HERCULES_STAGNATION_SOFT_LIMIT",
            "HERCULES_STAGNATION_HARD_LIMIT",
        ):
            monkeypatch.delenv(var, raising=False)
        assert stagnation_limits({}) == (3, 6)

    def test_config_override(self, monkeypatch):
        for var in (
            "HERCULES_STAGNATION_SOFT_LIMIT",
            "HERCULES_STAGNATION_HARD_LIMIT",
        ):
            monkeypatch.delenv(var, raising=False)
        cfg = {"agent": {"stagnation_soft_limit": 4, "stagnation_hard_limit": 9}}
        assert stagnation_limits(cfg) == (4, 9)

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("HERCULES_STAGNATION_SOFT_LIMIT", "2")
        monkeypatch.setenv("HERCULES_STAGNATION_HARD_LIMIT", "5")
        assert stagnation_limits({}) == (2, 5)

    def test_inverted_limits_normalized(self, monkeypatch):
        for var in (
            "HERCULES_STAGNATION_SOFT_LIMIT",
            "HERCULES_STAGNATION_HARD_LIMIT",
        ):
            monkeypatch.delenv(var, raising=False)
        # hard <= soft must be repaired so hard leaves room after soft.
        soft, hard = stagnation_limits(
            {"agent": {"stagnation_soft_limit": 5, "stagnation_hard_limit": 3}}
        )
        assert soft == 5
        assert hard > soft

    def test_soft_below_two_falls_back(self, monkeypatch):
        for var in (
            "HERCULES_STAGNATION_SOFT_LIMIT",
            "HERCULES_STAGNATION_HARD_LIMIT",
        ):
            monkeypatch.delenv(var, raising=False)
        soft, hard = stagnation_limits({"agent": {"stagnation_soft_limit": 1}})
        assert soft == 3
        assert hard > soft

    def test_garbage_values_fall_back(self, monkeypatch):
        monkeypatch.setenv("HERCULES_STAGNATION_SOFT_LIMIT", "not-a-number")
        monkeypatch.delenv("HERCULES_STAGNATION_HARD_LIMIT", raising=False)
        soft, hard = stagnation_limits({})
        assert (soft, hard) == (3, 6)


class TestMessages:
    def test_nudge_mentions_count_and_tool(self):
        msg = build_stagnation_nudge(3, ["read_file"])
        assert "3 times" in msg
        assert "read_file" in msg
        assert msg.startswith("[System:")

    def test_nudge_single_vs_multiple_tools(self):
        one = build_stagnation_nudge(3, ["read_file"])
        many = build_stagnation_nudge(3, ["read_file", "grep", "terminal"])
        assert "read_file" in one
        assert "grep" in many

    def test_nudge_dedupes_tool_names(self):
        msg = build_stagnation_nudge(4, ["read_file", "read_file"])
        # Name should appear once in the rendered list, not duplicated.
        assert msg.count("`read_file`") == 1

    def test_halt_message_is_user_facing(self):
        msg = build_stagnation_halt_message(6, ["terminal"])
        assert "terminal" in msg
        # Not a bracketed system directive — it is shown to the user.
        assert not msg.startswith("[System")
        assert "repeating" in msg.lower()

    def test_empty_tool_names_have_safe_fallback(self):
        assert "the same tool call" in build_stagnation_nudge(3, [])
        assert "the same tool call" in build_stagnation_halt_message(6, [])


class TestRunLengthSemantics:
    """Simulate the loop's counter to pin the soft->hard escalation shape."""

    def _run(self, fingerprints, soft, hard):
        """Mimic the loop's per-turn counter updates; return event log."""
        last_fp = ""
        run = 0
        nudged = False
        events = []
        for fp in fingerprints:
            if fp and fp == last_fp:
                run += 1
            else:
                last_fp = fp
                run = 1 if fp else 0
                nudged = False
            if fp and run >= hard:
                events.append(("halt", run))
                break
            if fp and run >= soft and not nudged:
                events.append(("nudge", run))
                nudged = True
        return events

    def test_repeated_call_nudges_then_halts(self):
        fps = ["x"] * 10
        events = self._run(fps, soft=3, hard=6)
        assert ("nudge", 3) in events
        assert ("halt", 6) in events
        # Only one nudge, and halt ends the run.
        assert [e[0] for e in events] == ["nudge", "halt"]

    def test_progress_resets_counter(self):
        # Two repeats, then a different call, then repeats again: never reaches
        # the hard limit because the change in between resets the run.
        fps = ["x", "x", "y", "x", "x"]
        events = self._run(fps, soft=3, hard=6)
        assert events == []

    def test_alternating_does_not_trip(self):
        fps = ["x", "y"] * 20
        events = self._run(fps, soft=3, hard=6)
        assert events == []


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([os.path.abspath(__file__), "-v"]))
