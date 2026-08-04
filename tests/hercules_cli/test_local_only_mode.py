"""Local-only mode: the agent may only reach local inference servers.

When ``providers.local_only`` is set, ``resolve_runtime_provider`` must reject
any resolved endpoint that is not a loopback/LAN address — that is what makes
the deployment cloud-free regardless of which provider or model is configured.
The gate is on the *resolved endpoint*, so a "custom" provider pointed at a
cloud URL is caught just like a named cloud provider.
"""

import pytest

from hercules_cli import runtime_provider as rp


class TestEndpointLocality:
    @pytest.mark.parametrize(
        "url",
        [
            "http://localhost:11434/v1",       # Ollama
            "http://127.0.0.1:8000/v1",        # vLLM
            "http://0.0.0.0:8080/v1",          # llama-server bound to all ifaces
            "http://[::1]:5000/v1",            # TabbyAPI over IPv6 loopback
            "http://192.168.1.50:8000/v1",     # LAN
            "http://10.0.0.5:11434/v1",        # LAN
            "http://172.16.3.9:8080/v1",       # LAN
            "http://100.101.102.103:8000/v1",  # Tailscale CGNAT
            "http://gpu-box:8000/v1",          # bare single-label hostname
            "http://ollama.local:11434/v1",    # mDNS
            "http://server.internal:8000/v1",  # internal DNS
            "moa://local",                     # virtual aggregator scheme
        ],
    )
    def test_local_endpoints_pass(self, url):
        assert rp._is_local_endpoint(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "https://api.openai.com/v1",
            "https://api.anthropic.com",
            "https://openrouter.ai/api/v1",
            "https://generativelanguage.googleapis.com",
            "https://ollama.com/v1",           # Ollama CLOUD — not local
            "https://api.groq.com/openai/v1",
            "",                                 # no endpoint is not provably local
        ],
    )
    def test_cloud_endpoints_fail(self, url):
        assert rp._is_local_endpoint(url) is False


class TestConfigTruthy:
    @pytest.mark.parametrize(
        "value,expected",
        [
            (True, True), (False, False),
            (1, True), (0, False),
            ("true", True), ("True", True), ("1", True), ("yes", True), ("on", True),
            ("false", False), ("no", False), ("", False), ("off", False),
            (None, False),
        ],
    )
    def test_truthy(self, value, expected):
        assert rp._config_truthy(value) is expected


class TestEnforcement:
    def _cloud(self):
        return {"provider": "openai-api", "base_url": "https://api.openai.com/v1", "api_key": "sk-x"}

    def _local(self):
        return {"provider": "custom", "base_url": "http://localhost:11434/v1", "api_key": "x"}

    def test_disabled_lets_cloud_through(self, monkeypatch):
        monkeypatch.setattr(rp, "local_only_mode_enabled", lambda: False)
        out = rp._enforce_local_only(self._cloud())
        assert out["base_url"] == "https://api.openai.com/v1"

    def test_enabled_allows_local(self, monkeypatch):
        monkeypatch.setattr(rp, "local_only_mode_enabled", lambda: True)
        out = rp._enforce_local_only(self._local())
        assert out["base_url"] == "http://localhost:11434/v1"

    def test_enabled_blocks_cloud(self, monkeypatch):
        monkeypatch.setattr(rp, "local_only_mode_enabled", lambda: True)
        with pytest.raises(rp.LocalOnlyModeError) as exc:
            rp._enforce_local_only(self._cloud())
        msg = str(exc.value)
        # Actionable: names the mode, the offending endpoint, and a fix.
        assert "providers.local_only" in msg
        assert "api.openai.com" in msg
        assert "config set" in msg

    def test_custom_provider_pointed_at_cloud_is_blocked(self, monkeypatch):
        """The core case: a local-sounding provider must not smuggle a cloud URL."""
        monkeypatch.setattr(rp, "local_only_mode_enabled", lambda: True)
        runtime = {"provider": "custom", "base_url": "https://api.anthropic.com", "api_key": "x"}
        with pytest.raises(rp.LocalOnlyModeError):
            rp._enforce_local_only(runtime)

    def test_error_is_an_auth_error(self):
        """Existing handlers catch AuthError; the new error must be caught too."""
        assert issubclass(rp.LocalOnlyModeError, rp.AuthError)


class TestChokepointIntegration:
    """The public resolver must apply the gate to whatever the impl returns."""

    def test_gate_applied_to_impl_result(self, monkeypatch):
        monkeypatch.setattr(rp, "local_only_mode_enabled", lambda: True)
        monkeypatch.setattr(
            rp, "_resolve_runtime_provider_impl",
            lambda **kw: {"provider": "openrouter", "base_url": "https://openrouter.ai/api/v1", "api_key": "k"},
        )
        with pytest.raises(rp.LocalOnlyModeError):
            rp.resolve_runtime_provider(requested="openrouter")

    def test_local_impl_result_passes_through(self, monkeypatch):
        monkeypatch.setattr(rp, "local_only_mode_enabled", lambda: True)
        monkeypatch.setattr(
            rp, "_resolve_runtime_provider_impl",
            lambda **kw: {"provider": "ollama", "base_url": "http://localhost:11434/v1", "api_key": "x"},
        )
        out = rp.resolve_runtime_provider(requested="ollama")
        assert out["provider"] == "ollama"


class TestConfigReading:
    def test_reads_providers_local_only(self, monkeypatch):
        monkeypatch.setattr(rp, "load_config", lambda: {"providers": {"local_only": True}})
        assert rp.local_only_mode_enabled() is True

    def test_defaults_false(self, monkeypatch):
        monkeypatch.setattr(rp, "load_config", lambda: {})
        assert rp.local_only_mode_enabled() is False

    def test_fails_safe_to_false_on_error(self, monkeypatch):
        def _boom():
            raise RuntimeError("config unreadable")
        monkeypatch.setattr(rp, "load_config", _boom)
        assert rp.local_only_mode_enabled() is False
