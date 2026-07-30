"""Kimi Code OAuth provider — reuse-the-CLI-creds path.

The provider reads the Kimi Code CLI's device-code login credentials
(~/.kimi/credentials/kimi-code.json) and uses the access token as a plain
Bearer against the OpenAI-compatible https://api.kimi.com/coding endpoint —
the same "reuse the CLI login" pattern as qwen-oauth. These tests exercise the
credential read/resolve/status path with a mocked creds file (no network).
"""

import json
import time

import pytest

from hercules_cli import auth as a


@pytest.fixture
def kimi_creds(tmp_path, monkeypatch):
    """Point the provider at a temp kimi-code.json and return a writer."""
    path = tmp_path / "kimi-code.json"
    monkeypatch.setenv("HERCULES_KIMI_OAUTH_CREDS_FILE", str(path))
    # Keep env base-url overrides out of the way for deterministic assertions.
    monkeypatch.delenv("KIMI_OAUTH_BASE_URL", raising=False)
    monkeypatch.delenv("KIMI_BASE_URL", raising=False)

    def _write(data: dict):
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    return _write


class TestRegistry:
    def test_provider_registered_as_oauth(self):
        entry = a.PROVIDER_REGISTRY["kimi-oauth"]
        assert entry.auth_type == "oauth_external"
        assert entry.inference_base_url == "https://api.kimi.com/coding"

    def test_default_base_url_constant(self):
        assert a.DEFAULT_KIMI_OAUTH_BASE_URL == "https://api.kimi.com/coding"


class TestResolve:
    def test_resolves_access_token_and_base_url(self, kimi_creds):
        kimi_creds({
            "access_token": "kc-abc123",
            "refresh_token": "kc-refresh",
            "expiry_date": int(time.time() * 1000) + 3_600_000,  # +1h
        })
        creds = a.resolve_kimi_oauth_runtime_credentials()
        assert creds["provider"] == "kimi-oauth"
        assert creds["api_key"] == "kc-abc123"
        assert creds["base_url"] == "https://api.kimi.com/coding"
        assert creds["source"] == "kimi-cli"

    def test_defensive_field_parsing_camelcase(self, kimi_creds):
        # Some CLI versions may camelCase the field — resolve must still work.
        kimi_creds({"accessToken": "kc-camel", "expiresAt": int(time.time()) + 3600})
        creds = a.resolve_kimi_oauth_runtime_credentials()
        assert creds["api_key"] == "kc-camel"

    def test_nested_token_object(self, kimi_creds):
        kimi_creds({"token": {"access_token": "kc-nested"}})
        creds = a.resolve_kimi_oauth_runtime_credentials(refresh_if_expiring=False)
        assert creds["api_key"] == "kc-nested"

    def test_base_url_env_override(self, kimi_creds, monkeypatch):
        kimi_creds({"access_token": "kc-x"})
        monkeypatch.setenv("KIMI_OAUTH_BASE_URL", "https://staging.kimi.example/coding/")
        creds = a.resolve_kimi_oauth_runtime_credentials(refresh_if_expiring=False)
        # trailing slash stripped
        assert creds["base_url"] == "https://staging.kimi.example/coding"

    def test_missing_creds_file_raises_actionable_error(self, tmp_path, monkeypatch):
        monkeypatch.setenv(
            "HERCULES_KIMI_OAUTH_CREDS_FILE", str(tmp_path / "absent.json")
        )
        with pytest.raises(a.AuthError) as exc:
            a.resolve_kimi_oauth_runtime_credentials()
        assert exc.value.code == "kimi_auth_missing"
        assert "Kimi Code" in str(exc.value)


class TestStatus:
    def test_logged_in_true_with_valid_creds(self, kimi_creds):
        kimi_creds({
            "access_token": "kc-live",
            "expiry_date": int(time.time() * 1000) + 3_600_000,
        })
        st = a.get_kimi_oauth_auth_status()
        assert st["logged_in"] is True
        assert st["source"] == "kimi-cli"

    def test_logged_out_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv(
            "HERCULES_KIMI_OAUTH_CREDS_FILE", str(tmp_path / "absent.json")
        )
        st = a.get_kimi_oauth_auth_status()
        assert st["logged_in"] is False
        assert "error" in st


class TestExpiry:
    def test_far_future_not_expiring(self):
        assert a._kimi_access_token_is_expiring(int(time.time() * 1000) + 3_600_000) is False

    def test_past_is_expiring(self):
        assert a._kimi_access_token_is_expiring(int(time.time() * 1000) - 1000) is True

    def test_unknown_expiry_not_expiring(self):
        # No expiry info → trust the CLI to keep the token fresh (don't refresh).
        assert a._kimi_access_token_is_expiring(None) is False

    def test_seconds_expiry_normalized_to_ms(self, kimi_creds):
        # A seconds-based expiry in the past must be detected as expiring.
        secs = int(time.time()) - 100
        assert a._kimi_expiry_ms({"expires_at": secs}) == secs * 1000


# ---------------------------------------------------------------------------
# Real in-app login: Device Authorization Grant (RFC 8628)
# ---------------------------------------------------------------------------

class _FakeResp:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._payload = payload if payload is not None else {}
        self.text = json.dumps(self._payload)

    def json(self):
        return self._payload


class _FakeClient:
    """Scripted httpx.Client stand-in for the device-code flow (no network)."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def post(self, url, headers=None, data=None):
        self.calls.append((url, data))
        return self._responses.pop(0)


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    """Isolate the auth store to a tmp HERCULES_HOME; no CLI creds file present."""
    monkeypatch.setenv("HERCULES_HOME", str(tmp_path / "hho"))
    monkeypatch.setenv("HERCULES_KIMI_OAUTH_CREDS_FILE", str(tmp_path / "none.json"))
    monkeypatch.delenv("KIMI_OAUTH_BASE_URL", raising=False)
    monkeypatch.delenv("KIMI_BASE_URL", raising=False)
    monkeypatch.delenv("KIMI_OAUTH_DEVICE_CODE_URL", raising=False)
    return tmp_path


class TestDeviceCodeLogin:
    def test_login_persists_tokens_and_reports_logged_in(self, isolated_home, monkeypatch):
        device = _FakeResp(200, {
            "device_code": "dev-1", "user_code": "ABCD-1234",
            "verification_uri": "https://kimi.com/device",
            "verification_uri_complete": "https://kimi.com/device?code=ABCD-1234",
            "expires_in": 900, "interval": 1,
        })
        token = _FakeResp(200, {
            "access_token": "kc-live", "refresh_token": "kc-r",
            "expires_in": 3600, "token_type": "Bearer",
        })
        client = _FakeClient([device, token])
        monkeypatch.setattr(a.httpx, "Client", lambda *args, **kw: client)

        status = a.kimi_oauth_device_code_login(open_browser=False)
        assert status["logged_in"] is True
        assert status["source"] == "device-code"

        # Persisted to the auth store — a fresh resolve returns it.
        creds = a.resolve_kimi_oauth_runtime_credentials(refresh_if_expiring=False)
        assert creds["api_key"] == "kc-live"
        assert creds["source"] == "device-code"

    def test_device_endpoint_fallback_on_404(self, isolated_home, monkeypatch):
        # First candidate 404s; the flow falls through to the next endpoint.
        r404 = _FakeResp(404, {"error": "not_found"})
        device = _FakeResp(200, {
            "device_code": "d", "user_code": "U",
            "verification_uri": "https://k/", "expires_in": 900, "interval": 1,
        })
        token = _FakeResp(200, {"access_token": "kc", "refresh_token": "r", "expires_in": 3600})
        client = _FakeClient([r404, device, token])
        monkeypatch.setattr(a.httpx, "Client", lambda *args, **kw: client)

        status = a.kimi_oauth_device_code_login(open_browser=False)
        assert status["logged_in"] is True
        # The successful device request used the 2nd candidate path.
        assert client.calls[1][0].endswith("/api/oauth/device/code")

    def test_all_endpoints_404_raises_actionable_error(self, isolated_home, monkeypatch):
        client = _FakeClient([_FakeResp(404, {"error": "nf"}), _FakeResp(404, {"error": "nf"})])
        monkeypatch.setattr(a.httpx, "Client", lambda *args, **kw: client)
        with pytest.raises(a.AuthError) as ei:
            a.kimi_oauth_device_code_login(open_browser=False)
        assert ei.value.code == "kimi_device_code_endpoint_unknown"

    def test_authstore_login_preferred_over_cli_file(self, isolated_home, monkeypatch):
        # Both a CLI creds file and a Hercules device-code login exist → store wins.
        cli = isolated_home / "kimi-code.json"
        cli.write_text(json.dumps({"access_token": "from-cli"}), encoding="utf-8")
        monkeypatch.setenv("HERCULES_KIMI_OAUTH_CREDS_FILE", str(cli))
        a._save_kimi_oauth_tokens({"access_token": "from-store"}, base_url="https://api.kimi.com/coding")

        creds = a.resolve_kimi_oauth_runtime_credentials(refresh_if_expiring=False)
        assert creds["api_key"] == "from-store"
        assert creds["source"] == "device-code"

    def test_device_code_url_env_override_wins(self, isolated_home, monkeypatch):
        monkeypatch.setenv("KIMI_OAUTH_DEVICE_CODE_URL", "https://example.test/dev")
        urls = a._kimi_oauth_device_code_urls()
        assert urls == ["https://example.test/dev"]


class TestRuntimeApiMode:
    """api.kimi.com/coding speaks the Anthropic Messages protocol.

    Regression for the post-login 404: kimi-oauth was routed as
    chat_completions, sending requests to /coding/chat/completions which the
    endpoint answers with HTTP 404 resource_not_found.
    """

    def test_kimi_oauth_resolves_to_anthropic_messages(self):
        from types import SimpleNamespace
        from hercules_cli.runtime_provider import _resolve_runtime_from_pool_entry

        entry = SimpleNamespace(
            runtime_base_url="", base_url="", runtime_api_key="eyJfake.jwt.token",
            access_token="eyJfake.jwt.token", source="pool",
        )
        resolved = _resolve_runtime_from_pool_entry(
            provider="kimi-oauth", entry=entry,
            requested_provider="kimi-oauth", model_cfg={},
        )
        assert resolved["api_mode"] == "anthropic_messages"
        assert resolved["base_url"] == "https://api.kimi.com/coding"

    def test_fallback_model_list_has_no_legacy_moonshot_ids(self):
        # moonshot-v1-* only exists on platform.moonshot.ai, not /coding —
        # offering it produced resource_not_found 404s after login.
        from hercules_cli.models import _PROVIDER_MODELS
        catalog = _PROVIDER_MODELS.get("kimi-coding") or []
        assert catalog, "kimi-coding catalog missing"
        assert not any(m.startswith("moonshot-v1") for m in catalog)

    def test_resolve_runtime_provider_direct_path_uses_anthropic_messages(
        self, isolated_home, monkeypatch
    ):
        # The live-session path: resolve_runtime_provider's direct kimi-oauth
        # branch (not the pool-entry path) must also route anthropic_messages.
        # This branch served the post-login 404s even after the pool-entry fix.
        import hercules_cli.runtime_provider as rp

        monkeypatch.setattr(
            rp,
            "resolve_kimi_oauth_runtime_credentials",
            lambda **kw: {
                "provider": "kimi-oauth",
                "base_url": "https://api.kimi.com/coding",
                "api_key": "eyJfake.jwt.token",
                "source": "device-code",
                "expires_at_ms": None,
            },
        )
        resolved = rp.resolve_runtime_provider(requested="kimi-oauth")
        assert resolved["provider"] == "kimi-oauth"
        assert resolved["api_mode"] == "anthropic_messages"
        assert resolved["base_url"] == "https://api.kimi.com/coding"

    def test_overlay_transport_is_anthropic_messages(self):
        from hercules_cli.providers import HERCULES_OVERLAYS
        assert HERCULES_OVERLAYS["kimi-oauth"].transport == "anthropic_messages"
