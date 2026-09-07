"""Docker update guidance is Cooklabs GHCR, not Nous Docker Hub."""

from __future__ import annotations

import pytest


class TestCooklabsDockerUpdate:
    @pytest.fixture(autouse=True)
    def _setup_test_client(self, monkeypatch, _isolate_hercules_home):
        try:
            from starlette.testclient import TestClient
        except ImportError:
            pytest.skip("fastapi/starlette not installed")

        import hercules_state
        from hercules_constants import get_hercules_home
        from hercules_cli.web_server import app, _SESSION_HEADER_NAME, _SESSION_TOKEN

        monkeypatch.setattr(hercules_state, "DEFAULT_DB_PATH", get_hercules_home() / "state.db")
        self.client = TestClient(app)
        self.client.headers[_SESSION_HEADER_NAME] = _SESSION_TOKEN

    def test_update_hercules_returns_cooklabs_docker_guidance(self, monkeypatch):
        import hercules_cli.web_server as web_server

        spawned = False

        def fail_spawn(*_args, **_kwargs):
            nonlocal spawned
            spawned = True
            raise AssertionError("docker update guard should not spawn hercules update")

        monkeypatch.setattr(web_server, "_dashboard_local_update_managed_externally", lambda: False)
        monkeypatch.setattr(web_server, "detect_install_method", lambda _root: "docker")
        monkeypatch.setattr(web_server, "_spawn_hercules_action", fail_spawn)
        web_server._ACTION_PROCS.pop("hercules-update", None)
        web_server._ACTION_RESULTS.pop("hercules-update", None)

        resp = self.client.post("/api/hercules/update")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False
        assert data["name"] == "hercules-update"
        assert data["pid"] is None
        assert data["error"] == "docker_update_unsupported"
        msg = data["message"]
        assert "nousresearch/hercules-agent" not in msg
        assert "ghcr.io" in msg or "Dockerfile" in msg
        assert spawned is False

        status = self.client.get("/api/actions/hercules-update/status")
        assert status.status_code == 200
        status_data = status.json()
        assert status_data["running"] is False
        blob = "\n".join(status_data.get("lines") or [])
        assert "nousresearch/hercules-agent" not in blob
