"""Auto-recovery ladder: after api_max_retries and the fallback chain are spent
on a transient outage, the turn waits and retries (agent.auto_recovery_cycles)
instead of ending in "API call failed after N retries"."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from agent.error_classifier import FailoverReason
from agent.turn_recovery_autorecover import (
    ladder_eligible,
    ladder_notice,
    ladder_wait_seconds,
    next_recovery_wait,
    wait_interruptibly,
)
from agent.turn_retry_state import TurnRetryState
from run_agent import AIAgent


def _make_agent(cycles: int) -> AIAgent:
    with (
        patch("run_agent.get_tool_definitions", return_value=[]),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI"),
    ):
        a = AIAgent(
            api_key="test-key-1234567890",
            base_url="https://api.openai.com/v1",
            provider="openai",
            api_mode="chat_completions",
            model="gpt-5.5",
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
        )
    a.client = MagicMock()
    a._cached_system_prompt = "You are helpful."
    a._use_prompt_caching = False
    a.tool_delay = 0
    a.compression_enabled = False
    a.save_trajectories = False
    a._api_max_retries = 1
    a._auto_recovery_cycles = cycles
    return a


def _err_503():
    err = Exception("Error code: 503 - service unavailable")
    err.status_code = 503
    err.response = SimpleNamespace(headers={})
    return err


def _ok(text="recovered"):
    msg = SimpleNamespace(content=text, tool_calls=None, reasoning=None)
    choice = SimpleNamespace(message=msg, finish_reason="stop")
    return SimpleNamespace(choices=[choice], model="gpt-5.5", usage=None, id="r1")


def _run(agent, side_effect):
    agent.client.chat.completions.create.side_effect = side_effect
    statuses = []
    with (
        patch.object(agent, "_persist_session"),
        patch.object(agent, "_save_trajectory"),
        patch.object(agent, "_cleanup_task_resources"),
        patch.object(agent, "_emit_status", side_effect=statuses.append),
        patch("agent.turn_recovery_autorecover.ladder_wait_seconds", return_value=0.0),
    ):
        result = agent.run_conversation("hello")
    return result, statuses


class TestLadderInLoop:
    def test_transient_outage_recovers_within_cycles(self):
        agent = _make_agent(cycles=3)
        result, statuses = _run(agent, [_err_503(), _err_503(), _ok()])
        assert result.get("failed") is not True
        assert result["final_response"] == "recovered"
        assert agent.client.chat.completions.create.call_count == 3
        notices = [s for s in statuses if "retrying automatically" in s]
        assert len(notices) == 2
        assert "(cycle 1/3)" in notices[0] and "(cycle 2/3)" in notices[1]

    def test_gives_up_after_configured_cycles(self):
        agent = _make_agent(cycles=2)
        result, statuses = _run(agent, [_err_503()] * 10)
        assert result.get("failed") is True
        # 1 initial attempt + 2 recovery cycles (api_max_retries=1 each).
        assert agent.client.chat.completions.create.call_count == 3
        assert any("gave up after 2 cycles" in s for s in statuses)

    def test_zero_cycles_keeps_old_fail_fast_behavior(self):
        agent = _make_agent(cycles=0)
        result, statuses = _run(agent, [_err_503()] * 10)
        assert result.get("failed") is True
        assert agent.client.chat.completions.create.call_count == 1
        assert not any("retrying automatically" in s for s in statuses)


class TestLadderUnits:
    def _classified(self, reason):
        return SimpleNamespace(reason=reason)

    def test_only_transient_reasons_are_eligible(self):
        agent = SimpleNamespace(
            _auto_recovery_cycles=5,
            _current_streamed_assistant_text="",
            _has_content_after_think_block=lambda s: bool(s.strip()),
        )
        for reason in (
            FailoverReason.overloaded,
            FailoverReason.server_error,
            FailoverReason.timeout,
        ):
            assert ladder_eligible(agent, self._classified(reason))
        for reason in (
            FailoverReason.auth,
            FailoverReason.billing,
            FailoverReason.rate_limit,
        ):
            assert not ladder_eligible(agent, self._classified(reason))

    def test_not_eligible_once_answer_text_was_streamed(self):
        agent = SimpleNamespace(
            _auto_recovery_cycles=5,
            _current_streamed_assistant_text="partial answer",
            _has_content_after_think_block=lambda s: bool(s.strip()),
        )
        assert not ladder_eligible(agent, self._classified(FailoverReason.server_error))

    def test_schedule_and_retry_after_cap(self):
        no_header = SimpleNamespace(response=SimpleNamespace(headers={}))
        assert 15 <= ladder_wait_seconds(1, no_header) <= 15 * 1.2 + 0.01
        assert 60 <= ladder_wait_seconds(5, no_header) <= 60 * 1.2 + 0.01
        hinted = SimpleNamespace(
            response=SimpleNamespace(headers={"retry-after": "90"})
        )
        assert ladder_wait_seconds(1, hinted) == 90
        huge = SimpleNamespace(
            response=SimpleNamespace(headers={"retry-after": "9999"})
        )
        assert ladder_wait_seconds(1, huge) == 120

    def test_notice_names_the_stop_hint_per_surface(self):
        cli = ladder_notice(
            SimpleNamespace(platform="cli"), wait_s=15, cycle=1, total=5
        )
        assert cli.endswith("press Esc to stop") and "(cycle 1/5)" in cli
        cron = ladder_notice(
            SimpleNamespace(platform="cron"), wait_s=15, cycle=1, total=5
        )
        assert cron.endswith("(cycle 1/5)")
        tg = ladder_notice(
            SimpleNamespace(platform="telegram"), wait_s=15, cycle=1, total=5
        )
        assert tg.endswith("send /stop to cancel")

    def test_cycle_counter_and_exhaustion(self):
        statuses = []
        agent = SimpleNamespace(
            _auto_recovery_cycles=1,
            _current_streamed_assistant_text="",
            _has_content_after_think_block=lambda s: False,
            platform="cli",
            log_prefix="",
            _emit_status=statuses.append,
        )
        state = TurnRetryState()
        classified = SimpleNamespace(reason=FailoverReason.timeout)
        err = SimpleNamespace(response=SimpleNamespace(headers={"retry-after": "3"}))
        assert next_recovery_wait(agent, err, classified, state) == 3
        assert state.auto_recovery_cycles_used == 1
        assert next_recovery_wait(agent, err, classified, state) is None
        assert "gave up after 1 cycles" in statuses[-1]

    def test_wait_is_interruptible(self):
        agent = SimpleNamespace(_interrupt_requested=True)
        assert wait_interruptibly(agent, 30, "x") is True
        agent = SimpleNamespace(_interrupt_requested=False)
        assert wait_interruptibly(agent, 0.05, "x") is False


@pytest.mark.parametrize(
    "value,expected", [(None, 5), (0, 0), (2, 2), (-3, 0), ("bad", 5)]
)
def test_config_parsing(value, expected):
    cfg = {"agent": {}}
    if value is not None:
        cfg["agent"]["auto_recovery_cycles"] = value
    with (
        patch("run_agent.OpenAI"),
        patch("hercules_cli.config.load_config", return_value=cfg),
    ):
        agent = AIAgent(
            api_key="test-key",
            base_url="https://openrouter.ai/api/v1",
            model="test/model",
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
        )
    assert agent._auto_recovery_cycles == expected
