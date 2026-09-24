"""The force-open guardrail default must remain a default.

``tools.ungate`` replaces approval/write/skill-scan/device-denylist functions
process-wide so an operator running YOLO is never prompted. That is the
intended shipped behaviour. What was not intended is that it could not be
turned off:

* it assigned ``HERCULES_YOLO_MODE=1`` at import, overwriting an operator's
  explicit ``HERCULES_YOLO_MODE=0`` — and ``tools.approval`` freezes
  ``_YOLO_MODE_FROZEN`` from that variable at ITS import, so approvals were
  bypassed even for someone who had asked for them;
* the patching ran in every process that imported ``hercules_bootstrap``,
  which includes the pytest process, so every guard test in the tree was
  asserting against a stub that returns ``{"approved": True}``.

These tests pin the predicate itself rather than the patching, so they stay
meaningful regardless of which guards ungate happens to cover. They must not
import ``hercules_bootstrap`` — that would apply the patches to the test
process and defeat the point.
"""

import importlib
import os
import sys

import pytest


@pytest.fixture
def ungate(monkeypatch):
    """A freshly imported ``tools.ungate`` with a clean environment."""
    monkeypatch.delenv("HERCULES_YOLO_MODE", raising=False)
    monkeypatch.delenv("HERCULES_OPEN_GUARDRAILS", raising=False)
    sys.modules.pop("tools.ungate", None)
    module = importlib.import_module("tools.ungate")
    yield module
    sys.modules.pop("tools.ungate", None)


class TestOpenByDefault:
    def test_open_when_nothing_says_otherwise(self, ungate, monkeypatch):
        # The shipped default: no env vars, not a test process.
        monkeypatch.setattr(ungate, "_running_under_pytest", lambda: False)
        assert ungate.open_guardrails_enabled() is True

    def test_explicit_truthy_keeps_it_open(self, ungate, monkeypatch):
        monkeypatch.setattr(ungate, "_running_under_pytest", lambda: False)
        for value in ("1", "true", "yes", "on"):
            monkeypatch.setenv("HERCULES_YOLO_MODE", value)
            assert ungate.open_guardrails_enabled() is True, value


class TestOperatorOptOut:
    """An operator who asks for the guards must get them."""

    @pytest.mark.parametrize("value", ["0", "false", "no", "off"])
    def test_yolo_mode_off_closes_the_gates(self, ungate, monkeypatch, value):
        monkeypatch.setattr(ungate, "_running_under_pytest", lambda: False)
        monkeypatch.setenv("HERCULES_YOLO_MODE", value)
        assert ungate.open_guardrails_enabled() is False

    @pytest.mark.parametrize("value", ["0", "false", "no", "off"])
    def test_open_guardrails_off_closes_the_gates(self, ungate, monkeypatch, value):
        monkeypatch.setattr(ungate, "_running_under_pytest", lambda: False)
        monkeypatch.setenv("HERCULES_OPEN_GUARDRAILS", value)
        assert ungate.open_guardrails_enabled() is False

    def test_open_guardrails_wins_over_yolo_mode(self, ungate, monkeypatch):
        # The dedicated switch is checked first, so it can close the gates on
        # a host where YOLO is exported for other reasons.
        monkeypatch.setattr(ungate, "_running_under_pytest", lambda: False)
        monkeypatch.setenv("HERCULES_YOLO_MODE", "1")
        monkeypatch.setenv("HERCULES_OPEN_GUARDRAILS", "0")
        assert ungate.open_guardrails_enabled() is False

    def test_blank_value_is_not_an_opt_out(self, ungate, monkeypatch):
        # An exported-but-empty var is "unset", not "off" — otherwise a stray
        # `export HERCULES_YOLO_MODE=` in a shell profile silently re-gates a
        # machine the operator never configured.
        monkeypatch.setattr(ungate, "_running_under_pytest", lambda: False)
        monkeypatch.setenv("HERCULES_YOLO_MODE", "   ")
        assert ungate.open_guardrails_enabled() is True

    def test_apply_does_not_claim_yolo_when_opted_out(self, ungate, monkeypatch):
        """The regression that made the opt-out unreachable.

        ``apply()`` used to set ``HERCULES_YOLO_MODE=1`` unconditionally at
        import. ``tools.approval`` reads that variable once, at its own import,
        to freeze ``_YOLO_MODE_FROZEN`` — so the assignment bypassed approvals
        even on the path where no patching happened.
        """
        monkeypatch.setattr(ungate, "_running_under_pytest", lambda: False)
        monkeypatch.setenv("HERCULES_YOLO_MODE", "0")
        ungate.apply()
        assert os.environ["HERCULES_YOLO_MODE"] == "0"

    def test_apply_is_a_no_op_when_opted_out(self, ungate, monkeypatch):
        monkeypatch.setattr(ungate, "_running_under_pytest", lambda: False)
        monkeypatch.setenv("HERCULES_OPEN_GUARDRAILS", "0")
        ungate.apply()

        import tools.approval as ap

        # The real implementations, not ungate's always-approve stubs.
        assert ap.check_all_command_guards.__module__ != "tools.ungate"
        assert ap.detect_hardline_command.__module__ != "tools.ungate"


class TestTestProcessesKeepRealGuards:
    def test_pytest_is_detected(self, ungate):
        # This IS a pytest process, so the probe must say so.
        assert ungate._running_under_pytest() is True

    def test_guards_are_not_patched_under_pytest(self, ungate):
        assert ungate.open_guardrails_enabled() is False

    @pytest.mark.parametrize("var", ["HERCULES_YOLO_MODE", "HERCULES_OPEN_GUARDRAILS"])
    def test_exported_truthy_does_not_re_break_the_suite(
        self, ungate, monkeypatch, var
    ):
        """A truthy value must not override the pytest check.

        Someone who runs YOLO plausibly has ``HERCULES_YOLO_MODE=1`` exported
        in their shell. If that won, a bare ``pytest`` run would re-patch the
        guards and ~300 unrelated tests would fail with no hint why.
        """
        monkeypatch.setenv(var, "1")
        assert ungate.open_guardrails_enabled() is False

    def test_opt_out_still_wins_under_pytest(self, ungate, monkeypatch):
        # Asking for the guards gets the guards, everywhere.
        monkeypatch.setenv("HERCULES_YOLO_MODE", "0")
        assert ungate.open_guardrails_enabled() is False

    def test_real_guards_are_reachable_in_this_process(self):
        """The point of all of the above: a guard test can test a guard."""
        import tools.approval as ap

        assert ap.check_all_command_guards.__module__ != "tools.ungate"
