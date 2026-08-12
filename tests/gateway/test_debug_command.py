"""Tests for the gateway /debug command."""

from unittest.mock import patch

import pytest

from gateway.config import GatewayConfig, Platform
from gateway.platforms.base import MessageEvent
from gateway.session import SessionSource


def _make_event(text="/debug", platform=Platform.TELEGRAM,
                user_id="12345", chat_id="67890"):
    source = SessionSource(
        platform=platform,
        user_id=user_id,
        chat_id=chat_id,
        user_name="testuser",
    )
    return MessageEvent(text=text, source=source)


def _make_runner():
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig()
    runner.adapters = {}
    return runner


class TestHandleDebugCommand:
    @pytest.mark.asyncio
    async def test_debug_writes_local_report_without_token(self, tmp_path, monkeypatch):
        """No GitHub token: /debug writes a local file (no paste service)."""
        monkeypatch.setenv("HERCULES_HOME", str(tmp_path))
        runner = _make_runner()
        event = _make_event()

        # The pastebin symbol is gone entirely.
        import hercules_cli.debug as debug_mod
        assert not hasattr(debug_mod, "upload_to_pastebin")

        with patch("hercules_cli.debug._capture_dump", return_value="dump"), \
             patch("hercules_cli.debug.collect_debug_report", return_value="report-body"), \
             patch("hercules_cli.debug._github_token", return_value=None):
            result = await runner._handle_debug_command(event)

        # A local report file was written under HERCULES_HOME/debug-shares/.
        written = list((tmp_path / "debug-shares").rglob("report.md"))
        assert len(written) == 1
        assert written[0].read_text(encoding="utf-8") == "report-body"

        assert str(written[0]) in result
        # No paste URL anywhere.
        assert "paste.rs" not in result and "dpaste" not in result

    @pytest.mark.asyncio
    async def test_debug_routes_to_gist_with_token(self, tmp_path, monkeypatch):
        """With a GitHub token, /debug uploads a secret gist and returns its link."""
        monkeypatch.setenv("HERCULES_HOME", str(tmp_path))
        runner = _make_runner()
        event = _make_event()

        gist_url = "https://gist.github.com/mintoriakamoto/cafef00d"
        with patch("hercules_cli.debug._capture_dump", return_value="dump"), \
             patch("hercules_cli.debug.collect_debug_report", return_value="report-body"), \
             patch("hercules_cli.debug._github_token", return_value="ghp_test"), \
             patch("hercules_cli.debug._upload_to_github_gist", return_value=gist_url) as mock_gist:
            result = await runner._handle_debug_command(event)

        mock_gist.assert_called_once()
        assert gist_url in result
        # No local file written when the gist succeeds.
        assert not (tmp_path / "debug-shares").exists()
        assert "paste.rs" not in result

    @pytest.mark.asyncio
    async def test_debug_reports_write_failure(self, tmp_path, monkeypatch):
        """A local write failure is surfaced, not silently swallowed."""
        monkeypatch.setenv("HERCULES_HOME", str(tmp_path))
        runner = _make_runner()
        event = _make_event()

        with patch("hercules_cli.debug._capture_dump", return_value="dump"), \
             patch("hercules_cli.debug.collect_debug_report", return_value="report-body"), \
             patch("hercules_cli.debug._github_token", return_value=None), \
             patch("pathlib.Path.write_text", side_effect=OSError("disk full")):
            result = await runner._handle_debug_command(event)

        assert "paste.rs" not in result
        # Some error/notice is returned (the gateway.debug.upload_failed key).
        assert isinstance(result, str) and result
