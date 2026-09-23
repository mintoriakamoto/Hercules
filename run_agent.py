"""Compatibility shim — the AIAgent core now lives in ``hercules_agent.run_agent``.

The 5.8k-line agent core was relocated into the ``hercules_agent`` package so the
SDK package is the real home of the runtime (mirroring the ``hermes_agent`` layout),
instead of a hollow facade over a root-level module.

This shim is kept so the many existing ``import run_agent`` / ``from run_agent
import X`` call sites (including the eight ``agent/*`` ``_ra()`` lazy-import shims)
and the ``hercules-agent`` console entry point keep working unchanged during the
incremental migration. It aliases this module object to the package module in
``sys.modules`` so *every* attribute access — including underscore-prefixed names
and ``mock.patch("run_agent.<name>")`` targets — resolves identically to
``hercules_agent.run_agent``.
"""

from __future__ import annotations

import sys as _sys

from hercules_agent import run_agent as _impl

# Make ``run_agent`` and ``hercules_agent.run_agent`` the exact same module
# object. Any code doing ``import run_agent`` (or ``from run_agent import X``)
# after this point sees the real implementation module.
_sys.modules[__name__] = _impl
