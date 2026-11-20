"""Force-open Hercules guardrails at process start.

YOLO (no approval prompts) is the operator default. The hardline floor,
the user's ``approvals.deny`` list and the content scanners are never
removed; see :func:`apply`.

Open is the DEFAULT, not a fixed property of the process. Two callers must
be able to get the real guards back:

* **An operator who asks for them.** ``HERCULES_YOLO_MODE=0`` (or
  ``HERCULES_OPEN_GUARDRAILS=0``) turns the patching off. This module used
  to assign ``HERCULES_YOLO_MODE=1`` unconditionally at import, which
  overwrote an explicit opt-out and left no way to close the gates short of
  editing the source — "default on" with no off switch. ``hercules_bootstrap``
  sets its other operator defaults with ``os.environ.setdefault()`` for
  exactly this reason ("so the user can explicitly opt out"); this now
  follows that convention.
* **The test suite.** These patches replace module-level functions
  process-wide, so importing anything that reaches ``hercules_bootstrap``
  swapped the guards out inside the pytest process too — every test that
  asserts a guard blocks something was asserting against a stub that returns
  "approved". That is ~300 failures across the suite and, worse, means no
  guard in the tree can be verified at all. Under pytest the patching is
  skipped so tests exercise the real code; shipped behaviour is unchanged.

``open_guardrails_enabled()`` is the single predicate, so other force-open
hooks (e.g. the media-delivery override in ``gateway.platforms``) gate on
the same answer instead of each inventing their own.
"""

from __future__ import annotations

import os
import sys

_applied = False


def _running_under_pytest() -> bool:
    """True when this process is a test run.

    ``PYTEST_CURRENT_TEST`` (the repo's usual probe, see
    ``hercules_cli.managed_scope``) is only set once a test item is running,
    and bootstrap is imported long before that — during collection, or at the
    first import in a conftest. ``sys.modules`` is what is already true at
    import time, so it is checked first.
    """
    if "pytest" in sys.modules or "_pytest" in sys.modules:
        return True
    return bool(os.environ.get("PYTEST_CURRENT_TEST"))


def open_guardrails_enabled() -> bool:
    """Whether guardrails should be force-opened in this process.

    Open is the default (the operator default is YOLO on). Two things close
    them, in this order:

    1. An explicit falsy ``HERCULES_OPEN_GUARDRAILS`` / ``HERCULES_YOLO_MODE``.
       This wins everywhere — asking for the guards always gets the guards.
    2. Running under pytest.

    A *truthy* value deliberately does NOT override the pytest check: it only
    restates the default. Letting it win would mean a developer with
    ``HERCULES_YOLO_MODE=1`` exported in their shell — the natural thing for
    someone who runs YOLO — silently re-patched the guards inside a bare
    ``pytest`` run and saw ~300 unrelated tests fail with no hint why.
    ``scripts/run_tests.sh`` runs hermetically (``env -i``) so the canonical
    path is unaffected either way; this covers the ad-hoc one. A test that
    genuinely wants the open behaviour can monkeypatch
    :func:`_running_under_pytest`.
    """
    for var in ("HERCULES_OPEN_GUARDRAILS", "HERCULES_YOLO_MODE"):
        raw = os.environ.get(var)
        if raw is None or not str(raw).strip():
            continue
        try:
            from utils import is_truthy_value

            opted_in = is_truthy_value(raw)
        except (ImportError, ModuleNotFoundError):
            opted_in = str(raw).strip().lower() not in {"0", "false", "no", "off"}
        if not opted_in:
            return False
        break
    return not _running_under_pytest()


def apply() -> None:
    """Turn YOLO on as the operator default, without removing the floor.

    YOLO means "do not prompt me": dangerous-pattern commands, execute_code
    and plugin tool approvals are auto-approved through the real gate's own
    yolo path. It does NOT mean "remove every check". The real gate still
    runs, so these keep working under YOLO:

    * the hardline floor (wiping /, home or system dirs, disk formatting,
      fork bombs, shutdown/reboot),
    * the user's own ``approvals.deny`` list,
    * the ``sudo -S`` password-guessing guard,
    * the memory injection scan, the skill install scan, the file-device
      denylist, and ``write_approval`` when the user has turned it on.

    Earlier versions replaced all of those with always-approve stubs, which
    also disarmed the user's own deny list and made every gateway caller's
    command run unchecked.
    """
    global _applied
    if _applied:
        return
    if not open_guardrails_enabled():
        return

    # Only claim the process once we know we are opening it: tools.approval
    # freezes _YOLO_MODE_FROZEN from this variable at ITS import.
    os.environ.setdefault("HERCULES_YOLO_MODE", "1")

    try:
        import tools.approval as ap

        # tools.approval may already have been imported (and frozen) before
        # bootstrap ran, so set the frozen flag directly as well.
        ap._YOLO_MODE_FROZEN = True
    except (ImportError, ModuleNotFoundError):
        pass

    _applied = True

apply()
