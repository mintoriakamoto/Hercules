"""Decision logic for turn-level local routing (agent/local_turn_routing.py).

These tests need no agent: they cover config parsing, the endpoint checks and
the pure ``decide_turn_route`` decision.  The runtime swap is covered in
tests/run_agent/test_local_turn_routing_runtime.py.
"""

from unittest.mock import MagicMock

import pytest

from agent import local_turn_routing as ltr
from agent.local_turn_routing import (
    LocalRoutingConfig,
    decide_turn_route,
    is_local_endpoint,
    probe_local_endpoint,
)


def _cfg(**overrides):
    base = {"enabled": True, "model": "qwen3:8b"}
    base.update(overrides)
    return LocalRoutingConfig(**base)


def _ok_probe(*_args, **_kwargs):
    return None


@pytest.fixture(autouse=True)
def _fresh_probe_cache():
    ltr.clear_probe_cache()
    yield
    ltr.clear_probe_cache()


class TestConfig:
    def test_missing_section_is_off(self):
        cfg = LocalRoutingConfig.from_config(None)
        assert cfg.enabled is False
        assert cfg.usable is False

    def test_defaults_are_safe(self):
        cfg = LocalRoutingConfig.from_config({"enabled": True, "model": "qwen3:8b"})
        assert cfg.usable
        assert cfg.base_url == "http://localhost:11434/v1"
        assert cfg.fallback_to_primary is False
        assert cfg.allow_non_local_endpoint is False
        assert cfg.health_check is True
        assert cfg.announce is True
        # Explicit key so the custom resolver never falls back to OPENAI_API_KEY.
        assert cfg.api_key == "ollama"

    def test_enabled_without_model_is_not_usable(self):
        assert not LocalRoutingConfig.from_config({"enabled": True}).usable

    def test_string_and_bad_values_are_coerced(self):
        cfg = LocalRoutingConfig.from_config(
            {
                "enabled": "yes",
                "model": " llama3.2 ",
                "max_message_chars": "nope",
                "max_request_tokens": -5,
                "fallback_to_primary": "true",
            }
        )
        assert cfg.enabled is True
        assert cfg.model == "llama3.2"
        assert cfg.max_message_chars == 400
        assert cfg.max_request_tokens == 24000
        assert cfg.fallback_to_primary is True

    def test_non_dict_section_is_off(self):
        assert LocalRoutingConfig.from_config("on").enabled is False


class TestIsLocalEndpoint:
    @pytest.mark.parametrize(
        "url",
        [
            "http://localhost:11434/v1",
            "http://127.0.0.1:11434/v1",
            "http://[::1]:11434/v1",
            "http://192.168.1.20:11434/v1",
            "http://10.0.0.5:1234/v1",
            "http://gpu-box.local:11434/v1",
            "http://host.docker.internal:11434/v1",
        ],
    )
    def test_local(self, url):
        assert is_local_endpoint(url)

    @pytest.mark.parametrize(
        "url",
        [
            "https://api.openai.com/v1",
            "https://ollama.com/v1",
            "https://openrouter.ai/api/v1",
            "http://8.8.8.8:11434/v1",
            "not a url",
            "",
        ],
    )
    def test_not_local(self, url):
        assert not is_local_endpoint(url)


class TestDecide:
    @pytest.mark.parametrize(
        "message",
        [
            "list the files in this folder",
            "check the git status",
            "count lines in run_agent.py",
            "find TODOs in agent/",
        ],
    )
    def test_simple_turns_go_local(self, message):
        route = decide_turn_route(message, _cfg(), request_tokens=4000, probe=_ok_probe)
        assert route.local is True
        assert route.model == "qwen3:8b"
        assert route.complexity == "simple"
        assert route.tier == "fast_cheap"

    @pytest.mark.parametrize(
        "message",
        [
            "design a plan for the new gateway",
            "check this code for security vulnerabilities",
            "explain how routing works",
        ],
    )
    def test_non_simple_turns_stay_on_primary(self, message):
        route = decide_turn_route(message, _cfg(), request_tokens=4000, probe=_ok_probe)
        assert route.local is False
        assert "router scored it" in route.reason

    def test_disabled(self):
        route = decide_turn_route(
            "list the files", _cfg(enabled=False), request_tokens=10, probe=_ok_probe
        )
        assert route.local is False

    def test_long_message_stays(self):
        route = decide_turn_route(
            "list " + "x" * 500, _cfg(), request_tokens=10, probe=_ok_probe
        )
        assert not route.local
        assert "longer than" in route.reason

    def test_code_block_stays(self):
        route = decide_turn_route(
            "check ```print(1)```", _cfg(), request_tokens=10, probe=_ok_probe
        )
        assert not route.local
        assert "code block" in route.reason

    def test_multimodal_stays(self):
        route = decide_turn_route(
            [{"type": "text", "text": "list files"}],
            _cfg(),
            request_tokens=10,
            probe=_ok_probe,
        )
        assert not route.local

    def test_request_too_big_for_local_model_stays(self):
        route = decide_turn_route(
            "list the files", _cfg(max_request_tokens=8000), request_tokens=9000,
            probe=_ok_probe,
        )
        assert not route.local
        assert "max_request_tokens" in route.reason

    def test_non_local_endpoint_is_refused(self):
        probe = MagicMock(return_value=None)
        route = decide_turn_route(
            "list the files",
            _cfg(base_url="https://ollama.com/v1"),
            request_tokens=10,
            probe=probe,
        )
        assert not route.local
        assert "not a local address" in route.reason
        probe.assert_not_called()

    def test_non_local_endpoint_allowed_by_flag(self):
        route = decide_turn_route(
            "list the files",
            _cfg(base_url="http://100.80.1.2:11434/v1", allow_non_local_endpoint=True),
            request_tokens=10,
            probe=_ok_probe,
        )
        assert route.local

    def test_unreachable_endpoint_stays(self):
        route = decide_turn_route(
            "list the files",
            _cfg(),
            request_tokens=10,
            probe=lambda *a, **k: "endpoint not reachable (ConnectionError)",
        )
        assert not route.local
        assert "not reachable" in route.reason

    def test_health_check_off_skips_probe(self):
        probe = MagicMock(return_value="down")
        route = decide_turn_route(
            "list the files", _cfg(health_check=False), request_tokens=10, probe=probe
        )
        assert route.local
        probe.assert_not_called()


class TestProbe:
    def _resp(self, status=200, ids=()):
        resp = MagicMock()
        resp.status_code = status
        resp.json.return_value = {"data": [{"id": i} for i in ids]}
        return resp

    def test_model_served(self, monkeypatch):
        get = MagicMock(return_value=self._resp(ids=["qwen3:8b", "llama3.2:latest"]))
        monkeypatch.setattr("requests.get", get)
        assert probe_local_endpoint("http://localhost:11434/v1/", "qwen3:8b") is None
        assert get.call_args.args[0] == "http://localhost:11434/v1/models"

    def test_untagged_name_matches_latest(self, monkeypatch):
        monkeypatch.setattr(
            "requests.get", MagicMock(return_value=self._resp(ids=["llama3.2:latest"]))
        )
        assert probe_local_endpoint("http://localhost:11434/v1", "llama3.2") is None

    def test_model_not_pulled(self, monkeypatch):
        monkeypatch.setattr(
            "requests.get", MagicMock(return_value=self._resp(ids=["llama3.2:latest"]))
        )
        reason = probe_local_endpoint("http://localhost:11434/v1", "qwen3:8b")
        assert "ollama pull qwen3:8b" in reason

    def test_http_error(self, monkeypatch):
        monkeypatch.setattr("requests.get", MagicMock(return_value=self._resp(500)))
        assert "HTTP 500" in probe_local_endpoint("http://localhost:1/v1", "m")

    def test_connection_refused(self, monkeypatch):
        monkeypatch.setattr("requests.get", MagicMock(side_effect=ConnectionError()))
        assert "not reachable" in probe_local_endpoint("http://localhost:1/v1", "m")

    def test_result_is_cached(self, monkeypatch):
        get = MagicMock(return_value=self._resp(ids=["m"]))
        monkeypatch.setattr("requests.get", get)
        probe_local_endpoint("http://localhost:1/v1", "m")
        probe_local_endpoint("http://localhost:1/v1", "m")
        assert get.call_count == 1
