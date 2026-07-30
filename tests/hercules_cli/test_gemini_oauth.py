"""Gemini OAuth reuse-creds layer — read/refresh ~/.gemini/oauth_creds.json.

Mirrors the qwen/kimi "reuse the CLI's login" pattern. Credential read/resolve/
status/expiry are exercised with a mocked creds file (no network).
"""

import json
import time

import pytest

from hercules_cli import auth as a


@pytest.fixture
def gemini_creds(tmp_path, monkeypatch):
    path = tmp_path / "oauth_creds.json"
    monkeypatch.setenv("HERCULES_GEMINI_OAUTH_CREDS_FILE", str(path))

    def _write(data: dict):
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    return _write


class TestResolve:
    def test_resolves_token(self, gemini_creds):
        gemini_creds({
            "access_token": "ya29.abc",
            "refresh_token": "1//refresh",
            "expiry_date": int(time.time() * 1000) + 3_600_000,
        })
        creds = a.resolve_gemini_oauth_runtime_credentials()
        assert creds["provider"] == "gemini-oauth"
        assert creds["api_key"] == "ya29.abc"
        assert creds["source"] == "gemini-cli"
        assert creds["base_url"].startswith("https://cloudcode-pa.googleapis.com")

    def test_missing_file_actionable_error(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERCULES_GEMINI_OAUTH_CREDS_FILE", str(tmp_path / "absent.json"))
        with pytest.raises(a.AuthError) as exc:
            a.resolve_gemini_oauth_runtime_credentials()
        assert exc.value.code == "gemini_auth_missing"
        assert "Gemini CLI" in str(exc.value)

    def test_client_id_is_public_gemini_cli_value(self):
        assert a._gemini_oauth_client_id().endswith(".apps.googleusercontent.com")
        assert a.GEMINI_OAUTH_TOKEN_URL == "https://oauth2.googleapis.com/token"


class TestStatus:
    def test_logged_in(self, gemini_creds):
        gemini_creds({"access_token": "ya29.live",
                      "expiry_date": int(time.time() * 1000) + 3_600_000})
        st = a.get_gemini_oauth_auth_status()
        assert st["logged_in"] is True
        assert st["source"] == "gemini-cli"

    def test_logged_out_no_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERCULES_GEMINI_OAUTH_CREDS_FILE", str(tmp_path / "absent.json"))
        st = a.get_gemini_oauth_auth_status()
        assert st["logged_in"] is False
        assert "error" in st


class TestExpiry:
    def test_far_future_not_expiring(self):
        assert a._gemini_access_token_is_expiring(int(time.time() * 1000) + 3_600_000) is False

    def test_past_expiring(self):
        assert a._gemini_access_token_is_expiring(int(time.time() * 1000) - 1000) is True

    def test_unknown_not_expiring(self):
        assert a._gemini_access_token_is_expiring(None) is False

    def test_expiry_ms_from_expiry_date(self):
        assert a._gemini_expiry_ms({"expiry_date": 1_700_000_000_000}) == 1_700_000_000_000

    def test_expiry_ms_from_seconds_expires_in(self):
        got = a._gemini_expiry_ms({"expires_in": 3600})
        assert got is not None and got > int(time.time() * 1000)


# ---------------------------------------------------------------------------
# Built-in "Login with Google" (no gemini-cli required)
# ---------------------------------------------------------------------------

class _FakeResp:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._payload = payload if payload is not None else {}
        self.text = json.dumps(self._payload)

    def json(self):
        return self._payload


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HERCULES_HOME", str(tmp_path / "hho"))
    monkeypatch.setenv("HERCULES_GEMINI_OAUTH_CREDS_FILE", str(tmp_path / "none.json"))
    monkeypatch.delenv("GEMINI_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("GEMINI_OAUTH_CLIENT_SECRET", raising=False)
    return tmp_path


class TestGoogleLogin:
    def test_missing_secret_and_failed_fetch_raises_actionable_error(
        self, isolated_home, monkeypatch
    ):
        # No embedded secret by design: with no env/creds secret AND the
        # auto-fetch failing, the login must point the user at the manual
        # GEMINI_OAUTH_CLIENT_SECRET fallback (published by Google).
        monkeypatch.setattr(a, "_fetch_published_gemini_client_secret", lambda **kw: "")
        with pytest.raises(a.AuthError) as ei:
            a.gemini_oauth_google_login(use_loopback=False)
        assert ei.value.code == "gemini_client_secret_missing"
        assert "GEMINI_OAUTH_CLIENT_SECRET" in str(ei.value)

    def test_auto_fetch_published_secret_enables_login(self, isolated_home, monkeypatch):
        # No env secret → the login fetches Google's published constant from
        # the public gemini-cli source and uses + persists it.
        fetched = "GOCSPX-" + "a" * 24
        oauth2_ts = f"export const OAUTH_CLIENT_SECRET = '{fetched}';"

        def fake_get(url, timeout=None, follow_redirects=None):
            assert "raw.githubusercontent.com/google-gemini/gemini-cli" in url
            return _FakeResp(200, None) if False else type(
                "R", (), {"status_code": 200, "text": oauth2_ts}
            )()

        exchanged = {}

        def fake_post(url, headers=None, data=None, timeout=None):
            exchanged.update(data or {})
            return _FakeResp(200, {
                "access_token": "ya29.fetched", "refresh_token": "1//r",
                "expires_in": 3600, "token_type": "Bearer",
            })

        monkeypatch.setattr(a.httpx, "get", fake_get)
        monkeypatch.setattr(a.httpx, "post", fake_post)
        monkeypatch.setattr("builtins.input", lambda prompt="": "code-1")

        status = a.gemini_oauth_google_login(use_loopback=False)
        assert status["logged_in"] is True
        assert exchanged["client_secret"] == fetched
        stored = a._read_gemini_oauth_authstore_tokens()
        assert stored and stored["client_secret"] == fetched

    def test_fetch_rejects_malformed_secret(self, isolated_home, monkeypatch):
        # A page not containing a GOCSPX-shaped constant must yield "" — never
        # forward arbitrary strings to Google's token endpoint.
        monkeypatch.setattr(a.httpx, "get", lambda *ar, **kw: type(
            "R", (), {"status_code": 200,
                      "text": "export const OAUTH_CLIENT_SECRET = 'evil value';"}
        )())
        assert a._fetch_published_gemini_client_secret() == ""

    def test_paste_flow_persists_tokens_and_reports_logged_in(
        self, isolated_home, monkeypatch
    ):
        exchanged = {}

        def fake_post(url, headers=None, data=None, timeout=None):
            exchanged.update(data or {})
            return _FakeResp(200, {
                "access_token": "ya29.live",
                "refresh_token": "1//r",
                "id_token": "eyJ.id",
                "expires_in": 3600,
                "token_type": "Bearer",
                "scope": "cloud-platform",
            })

        monkeypatch.setenv("GEMINI_OAUTH_CLIENT_SECRET", "test-secret")
        monkeypatch.setattr(a.httpx, "post", fake_post)
        monkeypatch.setattr("builtins.input", lambda prompt="": "  auth-code-123  ")

        status = a.gemini_oauth_google_login(use_loopback=False)
        assert status["logged_in"] is True
        assert status["source"] == "google-login"
        # Exchange used the pasted code, the no-browser redirect, and PKCE.
        assert exchanged["code"] == "auth-code-123"
        assert exchanged["redirect_uri"] == a.GEMINI_OAUTH_NO_BROWSER_REDIRECT_URI
        assert exchanged["grant_type"] == "authorization_code"
        assert exchanged["code_verifier"]

        # Persisted: a fresh resolve returns the store grant, no creds file.
        creds = a.resolve_gemini_oauth_runtime_credentials(refresh_if_expiring=False)
        assert creds["api_key"] == "ya29.live"
        assert creds["source"] == "google-login"

    def test_store_login_preferred_over_cli_file(self, isolated_home, monkeypatch):
        cli = isolated_home / "oauth_creds.json"
        cli.write_text(json.dumps({"access_token": "from-cli"}), encoding="utf-8")
        monkeypatch.setenv("HERCULES_GEMINI_OAUTH_CREDS_FILE", str(cli))
        a._save_gemini_oauth_tokens({"access_token": "from-store", "refresh_token": "r"})

        creds = a.resolve_gemini_oauth_runtime_credentials(refresh_if_expiring=False)
        assert creds["api_key"] == "from-store"
        assert creds["source"] == "google-login"

    def test_owned_login_refresh_persists_rotated_grant(self, isolated_home, monkeypatch):
        a._save_gemini_oauth_tokens({
            "access_token": "old",
            "refresh_token": "1//r",
            "client_id": "cid",
            "client_secret": "csec",
            "expiry_date": int(time.time() * 1000) - 1000,  # expired
        })

        def fake_post(url, headers=None, data=None, timeout=None):
            assert data["grant_type"] == "refresh_token"
            return _FakeResp(200, {"access_token": "new", "expires_in": 3600})

        monkeypatch.setattr(a.httpx, "post", fake_post)
        creds = a.resolve_gemini_oauth_runtime_credentials(refresh_if_expiring=True)
        assert creds["api_key"] == "new"
        # Rotated grant was written back to the store.
        stored = a._read_gemini_oauth_authstore_tokens()
        assert stored and stored["access_token"] == "new"

    def test_mark_active_preserves_stored_login(self, isolated_home):
        a._save_gemini_oauth_tokens({"access_token": "keep-me", "refresh_token": "r"})
        a._mark_gemini_oauth_active({"project": "proj-1"})
        stored = a._read_gemini_oauth_authstore_tokens()
        assert stored and stored["access_token"] == "keep-me"

    def test_state_mismatch_aborts(self, isolated_home, monkeypatch):
        monkeypatch.setenv("GEMINI_OAUTH_CLIENT_SECRET", "test-secret")
        monkeypatch.setattr(
            a,
            "_gemini_google_loopback_login",
            lambda authorize_url_for, timeout_seconds: {
                "code": "c", "state": "WRONG", "redirect_uri": "http://127.0.0.1:1/oauth2callback",
            },
        )
        with pytest.raises(a.AuthError) as ei:
            a.gemini_oauth_google_login(use_loopback=True)
        assert ei.value.code == "gemini_login_state_mismatch"
