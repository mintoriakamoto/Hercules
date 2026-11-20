"""Regression guard for the tools.approval public surface.

Commit 825ec3ac set the approval gates to permissive mode but, in doing so,
truncated tools/approval.py and dropped 126 top-level names. That broke import
of 23 production modules (gateway, ACP adapter, delegate/terminal/mcp tools,
every platform adapter) which reference the session-key contextvars, the
gateway-approval plumbing, and the content-trust manager.

This test pins the names that production code imports from tools.approval so a
future truncation fails here instead of at runtime import. It asserts presence
only; the floor's behaviour is pinned by test_floor_blocks_even_when_prompts_are_off.
"""

import importlib

import pytest

# Names imported by non-test production modules via `from tools.approval import ...`.
# Keep in sync with the module's public surface; a missing entry here means a
# production importer would crash at import time.
REQUIRED_APPROVAL_EXPORTS = (
    "_YOLO_MODE_FROZEN",
    "_get_approval_mode",
    "_is_spinner_paused",
    "_normalize_approval_mode",
    "check_all_command_guards",
    "check_execute_code_guard",
    "clear_session",
    "detect_dangerous_command",
    "detect_hardline_command",
    "disable_session_yolo",
    "enable_session_yolo",
    "get_current_session_key",
    "has_blocking_approval",
    "is_approval_bypass_active",
    "is_session_yolo_enabled",
    "load_permanent_allowlist",
    "register_gateway_notify",
    "request_elicitation_consent",
    "request_tool_approval",
    "reset_current_observability_context",
    "reset_current_session_key",
    "reset_hercules_interactive_context",
    "reset_hercules_spinner_pause_context",
    "resolve_gateway_approval",
    "set_current_observability_context",
    "set_current_session_key",
    "set_hercules_interactive_context",
    "set_hercules_spinner_pause_context",
    "unregister_gateway_notify",
)


@pytest.fixture(scope="module")
def approval_module():
    return importlib.import_module("tools.approval")


@pytest.mark.parametrize("name", REQUIRED_APPROVAL_EXPORTS)
def test_required_export_present(approval_module, name):
    assert hasattr(approval_module, name), (
        f"tools.approval is missing {name!r}; a production module imports it and "
        "would crash at import. Did an edit truncate the module?"
    )


def test_floor_blocks_even_when_prompts_are_off(approval_module, monkeypatch):
    """YOLO skips prompts; it never removes the hardline floor."""
    monkeypatch.setattr(approval_module, "_YOLO_MODE_FROZEN", True)
    assert approval_module.detect_hardline_command("rm -rf /")[0] is True
    assert approval_module.detect_dangerous_command("rm -rf /home/user")[0] is True
    for result in (
        approval_module.check_all_command_guards("rm -rf /", "local"),
        approval_module.check_dangerous_command("rm -rf /", "local"),
    ):
        assert result["approved"] is False
        assert result.get("hardline") is True
    # Ordinary dangerous commands are auto-approved under YOLO.
    assert approval_module.check_dangerous_command("rm -rf /tmp/x", "local")["approved"] is True
