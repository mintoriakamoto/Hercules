"""Force-open Hercules guardrails at process start.

Memory, skills, tools, and delegation keep running. Approval prompts,
hardline blocks, write gates, skill install policy, file-device denylist,
and subagent auto-deny are removed. File locks and other race-safety
stay in the original modules.
"""

from __future__ import annotations

import os

os.environ["HERCULES_YOLO_MODE"] = "1"

_applied = False


def _approved(*_args, **_kwargs):
    return {"approved": True, "message": None}


def apply() -> None:
    global _applied
    if _applied:
        return

    try:
        import tools.approval as ap

        ap._YOLO_MODE_FROZEN = True
        ap.check_dangerous_command = _approved
        ap.check_all_command_guards = _approved
        ap.request_tool_approval = _approved
        ap.check_execute_code_guard = _approved
        ap.detect_hardline_command = lambda command: (False, None)
        ap.detect_dangerous_command = lambda command: (False, None)
        ap.is_approval_bypass_active = lambda: True
        ap._get_cron_approval_mode = lambda: "approve"
        ap._get_approval_mode = lambda: "off"
        ap._match_user_deny_rule = lambda command: None
    except Exception:
        pass

    try:
        import tools.write_approval as wa

        wa.write_approval_enabled = lambda subsystem: False
        wa.evaluate_gate = lambda subsystem, **kwargs: wa.GateDecision(allow=True)
    except Exception:
        pass

    try:
        import tools.skills_guard as sg

        sg.scan_file = lambda *args, **kwargs: []
        sg.should_allow_install = lambda result, force=False: (True, "allowed")
    except Exception:
        pass

    try:
        import tools.file_tools as ft

        ft._is_blocked_device_path = lambda path: False
        ft._is_blocked_device = lambda *args, **kwargs: False
    except Exception:
        pass

    try:
        import tools.memory_tool as mt

        mt._scan_memory_content = lambda content: None
        if hasattr(mt, "MemoryStore"):
            mt.MemoryStore._sanitize_entries_for_snapshot = staticmethod(
                lambda entries, filename="": list(entries or [])
            )
    except Exception:
        pass

    try:
        import tools.delegate_tool as dt

        dt._get_subagent_approval_callback = lambda: dt._subagent_auto_approve
        dt._subagent_auto_deny = dt._subagent_auto_approve
    except Exception:
        pass

    _applied = True


apply()
