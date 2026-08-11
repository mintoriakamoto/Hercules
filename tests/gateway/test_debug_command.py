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
    async def test_debug_writes_local_report_and_does_not_upload(self, tmp_path, monkeypatch):
        """The pastebin upload route was removed: /debug writes a local file."""
        monkeypatch.setenv("HERCULES_HOME", str(tmp_path))
        runner = _make_runner()
        event = _make_event()

        # upload_to_pastebin no longer exists; if the handler tried to import or
        # call it the test would error. Assert no such symbol is used.
        import hercules_cli.debug as debug_mod
        assert not hasattr(debug_mod, "upload_to_pastebin")

        with patch("hercules_cli.debug._capture_dump", return_value="dump"), \
             patch("hercules_cli.debug.collect_debug_report", return_value="report-body"):
            result = await runner._handle_debug_command(event)

        # A local report file was written under HERCULES_HOME/debug-shares/.
        written = list((tmp_path / "debug-shares").rglob("report.md"))
        assert len(written) == 1
        assert written[0].read_text(encoding="utf-8") == "report-body"

        # The reply points at the local path and states nothing was uploaded.
        assert str(written[0]) in result
        assert "nothing was uploaded" in result.lower()
        # No paste URL anywhere.
        assert "paste.rs" not in result and "dpaste" not in result

    @pytest.mark.asyncio
    async def test_debug_reports_write_failure(self, tmp_path, monkeypatch):
        """A local write failure is surfaced, not silently swallowed."""
        monkeypatch.setenv("HERCULES_HOME", str(tmp_path))
        runner = _make_runner()
        event = _make_event()

        with patch("hercules_cli.debug._capture_dump", return_value="dump"), \
             patch("hercules_cli.debug.collect_debug_report", return_value="report-body"), \
             patch("pathlib.Path.write_text", side_effect=OSError("disk full")):
            result = await runner._handle_debug_command(event)

        assert "paste.rs" not in result
        # Some error/notice is returned (the gateway.debug.upload_failed key).
        assert isinstance(result, str) and result
