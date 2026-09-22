"""Tests for agent.replay_cleanup — shared replay-tail sanitizers.

These functions were extracted from gateway/run.py so every resume surface
(messaging gateway AND TUI/WebUI gateway) strips poisoned tool-call tails the
same way. Regression coverage for #29086 (WebUI session permanently stuck
because the dangling tool-call tail was replayed on every resume).
"""

from agent.replay_cleanup import (
    is_interrupted_tool_result,
    strip_dangling_tool_call_tail,
    strip_interrupted_tool_tails,
    sanitize_replay_history,
    canonicalize_replay_history,
)


def _user(text):
    return {"role": "user", "content": text}


def _assistant_tc(name):
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": name, "arguments": "{}"}}
        ],
    }


def _tool(content):
    return {"role": "tool", "tool_call_id": "c1", "content": content}


def test_is_interrupted_tool_result_markers():
    assert is_interrupted_tool_result("[Command interrupted]")
    assert is_interrupted_tool_result("foo\nexit_code: 130 (interrupt)\nbar")
    assert not is_interrupted_tool_result("exit_code: 0\nclean output")
    assert not is_interrupted_tool_result("ordinary tool output")
    assert not is_interrupted_tool_result(None)


def test_strip_dangling_tool_call_tail_removes_unanswered_read_only_tail():
    history = [_user("hi"), _assistant_tc("read_file")]
    out = strip_dangling_tool_call_tail(history)
    assert out == [_user("hi")]


def test_dangling_side_effect_is_recovered_as_unknown_not_erased():
    history = [_user("hi"), _assistant_tc("write_file")]

    out = strip_dangling_tool_call_tail(history)

    assert out[:-1] == history
    assert out[-1]["role"] == "tool"
    assert out[-1]["tool_call_id"] == "c1"
    assert out[-1]["effect_disposition"] == "unknown"
    assert "may have executed" in out[-1]["content"].lower()


def test_dangling_session_mutation_is_recovered_as_unknown():
    history = [_user("hi"), _assistant_tc("todo")]

    out = strip_dangling_tool_call_tail(history)

    assert out[:-1] == history
    assert out[-1]["effect_disposition"] == "unknown"
    assert "may have executed" in out[-1]["content"].lower()


def test_mixed_dangling_batch_uses_truthful_per_call_wording():
    assistant = {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {"id": "read", "function": {"name": "read_file", "arguments": "{}"}},
            {"id": "write", "function": {"name": "write_file", "arguments": "{}"}},
        ],
    }
    out = strip_dangling_tool_call_tail([_user("hi"), assistant])

    read_result, write_result = out[-2:]
    assert read_result["effect_disposition"] == "none"
    assert "no effect" in read_result["content"].lower()
    assert "unknown" not in read_result["content"].lower()
    assert write_result["effect_disposition"] == "unknown"
    assert "unknown" in write_result["content"].lower()


def test_strip_dangling_tool_call_tail_preserves_answered_pair():
    history = [_user("hi"), _assistant_tc("read_file"), _tool("contents")]
    out = strip_dangling_tool_call_tail(history)
    assert out == history  # answered -> untouched


def test_strip_interrupted_tool_tails_removes_interrupted_read_only_block():
    history = [_user("hi"), _assistant_tc("read_file"), _tool("[Command interrupted]")]
    out = strip_interrupted_tool_tails(history)
    assert out == [_user("hi")]


def test_interrupted_side_effect_is_preserved_as_unknown():
    history = [_user("hi"), _assistant_tc("terminal"), _tool("[Command interrupted]")]

    out = strip_interrupted_tool_tails(history)

    assert out[:-1] == history[:-1]
    assert out[-1]["role"] == "tool"
    assert out[-1]["effect_disposition"] == "unknown"


def test_strip_interrupted_tool_tails_preserves_successful_block():
    history = [_user("hi"), _assistant_tc("read_file"), _tool("ok"),
               {"role": "assistant", "content": "done"}]
    out = strip_interrupted_tool_tails(history)
    assert out == history


def test_strip_interrupted_tool_tails_removes_orphan_interrupted_tool():
    history = [_user("hi"), _tool("[Command interrupted] exit_code: 130 interrupt")]
    out = strip_interrupted_tool_tails(history)
    assert out == [_user("hi")]


def test_sanitize_replay_history_combines_both():
    # interrupted block is removed; a dangling read-only call is safe to erase
    history = [
        _user("first"),
        _assistant_tc("terminal"), _tool("[Command interrupted]"),
        _user("second"),
        _assistant_tc("read_file"),  # dangling
    ]
    out = sanitize_replay_history(history)
    assert out[:2] == [
        _user("first"),
        _assistant_tc("terminal"),
    ]
    assert out[2]["effect_disposition"] == "unknown"
    assert out[-1] == _user("second")


def test_sanitize_replay_history_noop_on_clean_history():
    history = [_user("hi"), {"role": "assistant", "content": "hello"}]
    assert sanitize_replay_history(history) == history


def test_sanitize_replay_history_empty():
    assert sanitize_replay_history([]) == []


def test_canonicalize_folds_all_three_transforms():
    # interrupted block + dangling tail + a stale dangerous confirmation, all
    # in one history — canonicalize must handle every one in a single pass.
    history = [
        {"role": "user", "content": "confirm forced restart", "timestamp": 0.0},
        {"role": "assistant", "content": "restarting"},
        _user("second"),
        _assistant_tc("terminal"), _tool("[Command interrupted]"),
        _user("third"),
        _assistant_tc("read_file"),  # dangling read-only tail
    ]
    out = canonicalize_replay_history(history, now=10_000.0)
    # stale confirmation redacted in place (role/position preserved)
    assert out[0]["role"] == "user"
    assert "EXPIRED" in out[0]["content"]
    # interrupted block removed, dangling read-only tail erased
    assert not any(is_interrupted_tool_result(m.get("content", "")) for m in out)
    assert out[-1] == _user("third")


def test_canonicalize_supersets_sanitize_on_stale_confirmation():
    # The exact divergence that broke the prefix cache: the TUI/WebUI path used
    # sanitize (2 passes) while the messaging gateway used all 3, so a stale
    # confirmation survived on one surface and not the other. canonicalize is
    # the complete pass every surface now shares.
    history = [{"role": "user", "content": "confirm shutdown", "timestamp": 0.0}]
    assert sanitize_replay_history(history)[0]["content"] == "confirm shutdown"
    assert "EXPIRED" in canonicalize_replay_history(history, now=10_000.0)[0]["content"]


def test_canonicalize_is_deterministic_for_a_shared_clock():
    # Two surfaces resuming the same session with the same admission clock must
    # serialize identical bytes — that is the whole point of the shared pass.
    history = [
        {"role": "user", "content": "confirm wipe", "timestamp": 0.0},
        {"role": "assistant", "content": "ok"},
        _user("later"),
        _assistant_tc("read_file"),  # dangling
    ]
    a = canonicalize_replay_history(history, now=5_000.0)
    b = canonicalize_replay_history(history, now=5_000.0)
    assert a == b
    # input is never mutated
    assert history[0]["content"] == "confirm wipe"


def test_canonicalize_empty():
    assert canonicalize_replay_history([]) == []
