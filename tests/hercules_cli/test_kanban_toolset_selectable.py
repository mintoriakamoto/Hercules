"""Kanban must be reachable from ``hercules tools``.

``tools/kanban_tools.py::_check_kanban_mode`` opens the kanban tools by two
routes: a dispatcher-spawned worker (``HERCULES_KANBAN_TASK`` set), or the
session's profile having ``kanban`` in its ``toolsets``. The second route was
unreachable from the UI — ``kanban`` was deliberately left out of
``CONFIGURABLE_TOOLSETS``, so the checklist never rendered a checkbox for it
and the only way in was hand-editing config.yaml. ``hercules doctor``
compounded it by reporting the toolset as "loaded only for dispatcher-spawned
workers", which describes the route the user *can't* take and hides the one
they can.

These tests pin the contract between the two halves: whatever the checklist
offers must be what the runtime gate reads.
"""

import os

import pytest

from hercules_cli.tools_config import (
    _DEFAULT_OFF_TOOLSETS,
    _checklist_toolset_keys,
    _get_effective_configurable_toolsets,
)


class TestKanbanIsOfferedByTheChecklist:
    def test_kanban_is_a_configurable_toolset(self):
        keys = {ts_key for ts_key, _, _ in _get_effective_configurable_toolsets()}
        assert "kanban" in keys

    def test_kanban_has_a_label_and_description(self):
        entry = next(
            (e for e in _get_effective_configurable_toolsets() if e[0] == "kanban"),
            None,
        )
        assert entry is not None
        _key, label, description = entry
        assert label.strip()
        assert description.strip()

    @pytest.mark.parametrize("platform", ["cli", "gateway", "telegram", "discord"])
    def test_offered_on_every_platform(self, platform):
        # Kanban carries no _TOOLSET_PLATFORM_RESTRICTIONS entry, so it is
        # configurable everywhere — orchestration is not a CLI-only concern.
        assert "kanban" in _checklist_toolset_keys(platform)

    def test_default_off(self):
        """Opt-in, not opt-out.

        Being in the checklist must not hand the kanban surface to every
        existing session on upgrade — the checkbox starts unticked.
        """
        assert "kanban" in _DEFAULT_OFF_TOOLSETS


class TestEnablingItActuallyOpensTheTools:
    """The point of the checkbox: the runtime gate must read what it writes."""

    @pytest.fixture
    def config_home(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERCULES_HOME", str(tmp_path))
        monkeypatch.delenv("HERCULES_KANBAN_TASK", raising=False)
        return tmp_path

    def _write_toolsets(self, home, toolsets):
        import yaml

        (home / "config.yaml").write_text(
            yaml.safe_dump({"toolsets": toolsets}), encoding="utf-8"
        )

    def test_gate_closed_without_the_toolset(self, config_home):
        import tools.kanban_tools as kt

        self._write_toolsets(config_home, ["hercules-cli"])
        assert kt._check_kanban_mode() is False

    def test_gate_opens_when_the_toolset_is_enabled(self, config_home):
        import tools.kanban_tools as kt

        self._write_toolsets(config_home, ["hercules-cli", "kanban"])
        assert kt._check_kanban_mode() is True

    def test_orchestrator_tools_open_too(self, config_home):
        """kanban_list / kanban_unblock are the orchestrator surface.

        They are hidden from task workers on purpose, so the profile route is
        the *only* way anything can reach them.
        """
        import tools.kanban_tools as kt

        self._write_toolsets(config_home, ["hercules-cli", "kanban"])
        assert kt._check_kanban_orchestrator_mode() is True

    def test_worker_env_still_opens_the_gate(self, config_home, monkeypatch):
        import tools.kanban_tools as kt

        self._write_toolsets(config_home, ["hercules-cli"])
        monkeypatch.setenv("HERCULES_KANBAN_TASK", "task-123")
        assert kt._check_kanban_mode() is True
        # ...and workers still don't get the board-routing tools.
        assert kt._check_kanban_orchestrator_mode() is False


class TestDoctorDescribesBothRoutes:
    def test_detail_mentions_the_toolset_route(self, monkeypatch):
        from hercules_cli.doctor import _doctor_tool_availability_detail

        monkeypatch.delenv("HERCULES_KANBAN_TASK", raising=False)
        detail = _doctor_tool_availability_detail("kanban")
        assert "toolset" in detail.lower(), detail
        # The old text named only the dispatcher route, which is the one a
        # user reading doctor cannot act on.
        assert "only for dispatcher-spawned workers" not in detail

    def test_no_detail_inside_a_worker(self, monkeypatch):
        from hercules_cli.doctor import _doctor_tool_availability_detail

        monkeypatch.setenv("HERCULES_KANBAN_TASK", "task-123")
        assert _doctor_tool_availability_detail("kanban") == ""

    def test_other_toolsets_unaffected(self):
        from hercules_cli.doctor import _doctor_tool_availability_detail

        assert _doctor_tool_availability_detail("web") == ""


class TestRegistryDescriptionMatchesTheGate:
    def test_toolset_description_names_both_routes(self):
        from toolsets import TOOLSETS

        description = TOOLSETS["kanban"]["description"]
        assert "HERCULES_KANBAN_TASK" in description
        # The orchestrator route must be documented where users read it.
        assert "toolset is enabled" in description
