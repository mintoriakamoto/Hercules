"""Tests for uv-tool install detection in the update path (issue #29700).

``uv tool install hercules-agent`` lives outside any venv, so the previous
``uv pip install --upgrade`` update path failed with ``No virtual
environment found``. ``is_uv_tool_install`` should detect this layout and
both the user-facing recommended command and the actual
``_cmd_update_pip`` subprocess invocation should switch to
``uv tool upgrade hercules-agent``.

Detection is restricted to properties of the running interpreter
(``sys.prefix`` / ``sys.executable``) so a pip/venv install on a machine
that also has ``uv tool install hercules-agent`` does not get misclassified.
"""
from __future__ import annotations

import subprocess
from types import SimpleNamespace
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Managed-uv compatibility for tests that patch shutil.which
# ---------------------------------------------------------------------------
# The production code now uses ``ensure_uv()`` / ``update_managed_uv()``
# instead of ``shutil.which("uv")``.  Many tests in this file patch
# ``shutil.which`` to control whether uv is "available" — these autouse
# fixtures make the managed_uv functions delegate to the patched
# ``shutil.which`` so the existing test setup keeps working without
# per-test changes.
@pytest.fixture(autouse=True)
def _patch_managed_uv(request):
    """Make managed_uv helpers follow shutil.which mocking in tests."""
    import shutil

    # resolve_uv delegates to shutil.which("uv") so that test patches
    # on shutil.which flow through naturally.
    def _fake_resolve_uv():
        return shutil.which("uv")

    def _fake_ensure_uv():
        return shutil.which("uv")

    def _fake_update_managed_uv():
        return None  # never actually self-update in tests

    with patch("hercules_cli.managed_uv.resolve_uv", side_effect=_fake_resolve_uv), \
         patch("hercules_cli.managed_uv.ensure_uv", side_effect=_fake_ensure_uv), \
         patch("hercules_cli.managed_uv.update_managed_uv", side_effect=_fake_update_managed_uv):
        yield


# ---------------------------------------------------------------------------
# is_uv_tool_install
# ---------------------------------------------------------------------------


class TestIsUvToolInstall:
    def test_returns_true_when_sys_prefix_matches_uv_tool_layout(self):
        from hercules_cli import config

        with patch.object(config.sys, "prefix", "/home/user/.local/share/uv/tools/hercules-agent"):
            assert config.is_uv_tool_install() is True

    def test_returns_true_when_sys_executable_matches_uv_tool_layout(self):
        """Some uv-tool layouts surface the marker on ``sys.executable`` (bin/python)."""
        from hercules_cli import config

        with patch.object(config.sys, "prefix", "/some/unrelated/venv"), \
             patch.object(
                 config.sys,
                 "executable",
                 "/home/user/.local/share/uv/tools/hercules-agent/bin/python",
             ):
            assert config.is_uv_tool_install() is True

    def test_returns_false_when_neither_prefix_nor_executable_matches(self):
        from hercules_cli import config

        with patch.object(config.sys, "prefix", "/some/unrelated/venv"), \
             patch.object(config.sys, "executable", "/usr/bin/python3"):
            assert config.is_uv_tool_install() is False

    def test_does_not_consult_uv_tool_list(self):
        """Detection must NOT shell out: ``uv tool list`` would false-positive
        when the active install is pip/venv but the machine also has
        ``uv tool install hercules-agent`` somewhere on disk. Copilot review on
        PR #29703 flagged this; the fix is to never call ``uv tool list``
        from the detection path."""
        from hercules_cli import config

        with patch.object(config.sys, "prefix", "/some/unrelated/venv"), \
             patch.object(config.sys, "executable", "/usr/bin/python3"), \
             patch("subprocess.run") as mock_run:
            assert config.is_uv_tool_install() is False
            mock_run.assert_not_called()

    def test_case_insensitive_match(self):
        """Match must be case-insensitive — Windows paths preserve case
        (e.g. ``...AppData\\Local\\UV\\Tools\\hercules-agent``) and a case-sensitive
        check would miss them. We exercise the lower-cased compare path here
        without monkey-patching ``os.sep``, which would break the whole suite."""
        from hercules_cli import config

        with patch.object(
            config.sys, "prefix", "/HOME/USER/.local/share/UV/Tools/hercules-agent"
        ):
            assert config.is_uv_tool_install() is True

    def test_handles_empty_executable(self):
        from hercules_cli import config

        with patch.object(config.sys, "prefix", "/some/unrelated/venv"), \
             patch.object(config.sys, "executable", ""):
            assert config.is_uv_tool_install() is False
