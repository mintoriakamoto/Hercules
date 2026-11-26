"""Runtime swap for turn-level local routing (agent/local_turn_routing.py).

Covers what the decision tests cannot: that a routed turn really moves the
agent onto the local endpoint, that the next turn always comes back to the
primary (even in a rate-limit cooldown), and that a failing local turn never
walks into a hosted ``fallback_providers`` entry unless
``fallback_to_primary`` is on.
"""

import time
from unittest.mock import MagicMock, patch

from agent.local_turn_routing import LocalRoutingConfig, apply_turn_route
from run_agent import AIAgent

PRIMARY_URL = "https://my-llm.example.com/v1"
LOCAL_URL = "http://localhost:11434/v1"
HOSTED_FALLBACK = {"provider": "openrouter", "model": "anthropic/claude-sonnet-4"}


def _tool_defs(*names):
    return [
        {
            "type": "function",
            "function": {
                "name": n,
                "description": f"{n} tool",
                "parameters": {"type": "object", "properties": {}},
            },
        }
        for n in names
    ]


def _passthrough_config(model=None, api_key=None, provider=None, base_url=None):
    # agent_init validates the constructor args through ConfigLoader, whose
    # provider list on main does not include "custom".  These tests are about
    # the runtime swap, not that list, so hand the args through unchanged.
    return {
        "model": model,
        "api_key": api_key,
        "provider": provider,
        "base_url": base_url,
    }


def _make_agent(fallback_model=None, **routing):
    with (
        patch(
            "agent.agent_init.ConfigLoader.load", side_effect=_passthrough_config
        ),
        patch("run_agent.get_tool_definitions", return_value=_tool_defs("web_search")),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI"),
    ):
        agent = AIAgent(
            api_key="test-key-12345678",
            base_url=PRIMARY_URL,
            provider="custom",
            model="primary-model",
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
            fallback_model=fallback_model,
        )
    agent.client = MagicMock()
    cfg = {"enabled": True, "model": "qwen3:8b", "health_check": False}
    cfg.update(routing)
    agent._local_routing_config = LocalRoutingConfig.from_config(cfg)
    agent._emit_status = MagicMock()
    agent._emit_warning = MagicMock()
    return agent


def _local_client():
    client = MagicMock()
    client.api_key = "ollama"
    client.base_url = LOCAL_URL
    return client


def _route(agent, message):
    with patch(
        "agent.auxiliary_client.resolve_provider_client",
        return_value=(_local_client(), "qwen3:8b"),
    ) as resolve:
        route = apply_turn_route(
            agent, message, [{"role": "user", "content": message}], "sys"
        )
    return route, resolve


class TestApply:
    def test_simple_turn_switches_to_local(self):
        agent = _make_agent()
        pool = MagicMock()
        agent._credential_pool = pool

        route, resolve = _route(agent, "list the files in this folder")

        assert route.local
        assert agent.model == "qwen3:8b"
        assert agent.base_url == LOCAL_URL
        assert agent.provider == "custom"
        assert agent.api_mode == "chat_completions"
        assert agent._fallback_activated is True
        assert agent._credential_pool is None
        assert agent._turn_route_state["credential_pool"] is pool
        agent._emit_status.assert_called_once()
        assert "qwen3:8b" in agent._emit_status.call_args.args[0]
        # The endpoint key is explicit: never a hosted key from the environment.
        kwargs = resolve.call_args.kwargs
        assert kwargs["explicit_api_key"] == "ollama"
        assert kwargs["explicit_base_url"] == LOCAL_URL

    def test_complex_turn_stays_on_primary(self):
        agent = _make_agent()
        route, resolve = _route(agent, "design a plan for the new gateway")
        assert not route.local
        assert agent.model == "primary-model"
        assert agent.base_url == PRIMARY_URL
        assert agent._turn_route_state is None
        resolve.assert_not_called()

    def test_off_by_default(self):
        agent = _make_agent(enabled=False)
        route, resolve = _route(agent, "list the files")
        assert not route.local
        assert agent.model == "primary-model"
        resolve.assert_not_called()

    def test_announce_off_is_silent(self):
        agent = _make_agent(announce=False)
        route, _ = _route(agent, "list the files")
        assert route.local
        agent._emit_status.assert_not_called()

    def test_delegated_child_is_skipped(self):
        agent = _make_agent()
        agent._delegate_depth = 1
        route, resolve = _route(agent, "list the files")
        assert not route.local
        resolve.assert_not_called()

    def test_client_build_failure_stays_on_primary(self):
        agent = _make_agent()
        with patch(
            "agent.auxiliary_client.resolve_provider_client", return_value=(None, None)
        ):
            route = apply_turn_route(agent, "list the files", [], "sys")
        assert not route.local
        assert agent.model == "primary-model"
        assert agent._turn_route_state is None


class TestRestore:
    def test_next_turn_restores_primary_and_pool(self):
        agent = _make_agent()
        pool = MagicMock()
        pool.provider = "custom"
        pool.has_available.return_value = False
        agent._credential_pool = pool
        _route(agent, "list the files")
        assert agent.model == "qwen3:8b"

        assert agent._restore_primary_runtime() is True
        assert agent.model == "primary-model"
        assert agent.base_url == PRIMARY_URL
        assert agent._fallback_activated is False
        assert agent._turn_route_state is None
        assert agent._credential_pool is pool

    def test_restore_ignores_rate_limit_cooldown_for_local_route(self):
        agent = _make_agent()
        _route(agent, "list the files")
        agent._rate_limited_until = time.monotonic() + 60
        assert agent._restore_primary_runtime() is True
        assert agent.model == "primary-model"


class TestLocalFailure:
    def test_no_hosted_fallback_by_default(self):
        agent = _make_agent(fallback_model=HOSTED_FALLBACK)
        _route(agent, "list the files")
        assert agent._has_pending_fallback() is False

        with patch("agent.auxiliary_client.resolve_provider_client") as resolve:
            assert agent._try_activate_fallback() is False
        resolve.assert_not_called()
        assert agent.model == "qwen3:8b"  # nothing moved to the hosted entry
        agent._emit_warning.assert_called_once()
        assert "fallback_to_primary" in agent._emit_warning.call_args.args[0]

    def test_fallback_to_primary_when_allowed(self):
        agent = _make_agent(fallback_model=HOSTED_FALLBACK, fallback_to_primary=True)
        _route(agent, "list the files")
        assert agent._has_pending_fallback() is True

        with patch("agent.auxiliary_client.resolve_provider_client") as resolve:
            assert agent._try_activate_fallback() is True
        resolve.assert_not_called()  # back to the primary, not the hosted fallback
        assert agent.model == "primary-model"
        assert agent.base_url == PRIMARY_URL
        assert agent._turn_route_state is None

    def test_normal_fallback_untouched_without_local_route(self):
        agent = _make_agent(fallback_model=HOSTED_FALLBACK)
        assert agent._has_pending_fallback() is True
