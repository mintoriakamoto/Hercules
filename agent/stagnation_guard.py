"""Cross-turn stagnation guard for the agent conversation loop.

The loop's existing ``_deduplicate_tool_calls`` only removes duplicate
``(name, arguments)`` pairs *within a single turn*. It does nothing about a
model that emits the *same* tool call, with the *same* arguments, turn after
turn — re-reading one file, re-running one failing command, oscillating on a
fixed point — until the iteration budget is spent. The result is identical, so
repeating it makes no progress; the run just burns tokens and wall-clock.

This module supplies the pure helpers the loop uses to detect that pattern:

* :func:`tool_calls_fingerprint` — an order-independent hash of a turn's tool
  calls, so two turns that issue the same set of calls fingerprint equal.
* :func:`stagnation_guard_enabled` / :func:`stagnation_limits` — the config
  gate and the ``(soft, hard)`` thresholds.
* :func:`build_stagnation_nudge` — the one-shot message injected at the soft
  limit, telling the model the repeated call cannot change and to alter its
  approach or stop.
* :func:`build_stagnation_halt_message` — the final message when the run keeps
  repeating to the hard limit and the loop stops it.

The loop owns the counters (``agent._stagnation_*``); these helpers stay pure so
they remain trivially testable and never touch agent state. Mirrors the
structure of :mod:`agent.verification_stop`.
"""

from __future__ import annotations

import hashlib
import os
from typing import Any, Iterable

# Defaults chosen so a normal retry-once pattern never trips: the soft nudge
# only fires on the 3rd identical turn in a row, the hard stop on the 6th. Both
# are overridable via config (``agent.stagnation_soft_limit`` /
# ``agent.stagnation_hard_limit``) or env.
_DEFAULT_SOFT_LIMIT = 3
_DEFAULT_HARD_LIMIT = 6


def tool_calls_fingerprint(tool_calls: Iterable[Any]) -> str:
    """Return an order-independent fingerprint of a turn's tool calls.

    Two turns issuing the same set of ``(name, arguments)`` pairs — in any
    order — fingerprint equal. An empty or unreadable call list returns ``""``,
    which the loop treats as "no fingerprint" (the guard never fires on turns
    that call no tools; those end the loop on their own).
    """
    pairs: list[str] = []
    for tc in tool_calls or []:
        try:
            name = tc.function.name
            arguments = tc.function.arguments
        except AttributeError:
            # Dict-shaped tool call (some transports hand these back).
            fn = tc.get("function", {}) if isinstance(tc, dict) else {}
            name = fn.get("name", "")
            arguments = fn.get("arguments", "")
        if name is None:
            name = ""
        if arguments is None:
            arguments = ""
        pairs.append(f"{name}\x00{arguments}")
    if not pairs:
        return ""
    # Sort so call order within the turn does not change the fingerprint.
    pairs.sort()
    digest = hashlib.sha256("\x01".join(pairs).encode("utf-8", "replace"))
    return digest.hexdigest()


def stagnation_guard_enabled(config: dict[str, Any] | None = None) -> bool:
    """Return whether the cross-turn stagnation guard is active.

    Precedence: an explicit ``HERCULES_STAGNATION_GUARD`` env var wins, then an
    explicit ``agent.stagnation_guard`` config value. Default ON — a loop stuck
    repeating one call is wasteful on every surface, interactive or not.
    """
    env = os.environ.get("HERCULES_STAGNATION_GUARD")
    if env is not None:
        return env.strip().lower() not in {"0", "false", "no", "off"}
    if config is None:
        try:
            from hercules_cli.config import load_config

            config = load_config()
        except Exception:
            config = {}
    agent_cfg = (config or {}).get("agent") if isinstance(config, dict) else None
    cfg_val = agent_cfg.get("stagnation_guard") if isinstance(agent_cfg, dict) else None
    if isinstance(cfg_val, bool):
        return cfg_val
    if isinstance(cfg_val, str):
        token = cfg_val.strip().lower()
        if token in {"0", "false", "no", "off"}:
            return False
        if token in {"1", "true", "yes", "on"}:
            return True
    # Missing or unrecognized value -> default ON.
    return True


def _read_positive_int(env_name: str, cfg: Any, fallback: int) -> int:
    raw = os.environ.get(env_name)
    if raw is None:
        raw = cfg
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return fallback
    return value if value > 0 else fallback


def stagnation_limits(config: dict[str, Any] | None = None) -> tuple[int, int]:
    """Return the ``(soft, hard)`` consecutive-repeat thresholds.

    ``soft`` is the run length that triggers a one-shot corrective nudge;
    ``hard`` is the run length at which the loop stops executing the repeated
    call and finishes. The pair is always normalized so ``2 <= soft < hard``;
    a misconfiguration that inverts or collapses them falls back to defaults
    rather than disabling the guard or nudging every turn.
    """
    if config is None:
        try:
            from hercules_cli.config import load_config

            config = load_config()
        except Exception:
            config = {}
    agent_cfg = (config or {}).get("agent") if isinstance(config, dict) else {}
    if not isinstance(agent_cfg, dict):
        agent_cfg = {}

    soft = _read_positive_int(
        "HERCULES_STAGNATION_SOFT_LIMIT",
        agent_cfg.get("stagnation_soft_limit"),
        _DEFAULT_SOFT_LIMIT,
    )
    hard = _read_positive_int(
        "HERCULES_STAGNATION_HARD_LIMIT",
        agent_cfg.get("stagnation_hard_limit"),
        _DEFAULT_HARD_LIMIT,
    )

    # A soft limit of 1 would nudge after a single call; require at least 2 so
    # the first repeat (turn 2) is what starts the count toward a nudge.
    if soft < 2:
        soft = _DEFAULT_SOFT_LIMIT
    # Hard must leave room for the model to react to the soft nudge.
    if hard <= soft:
        hard = soft + max(1, _DEFAULT_HARD_LIMIT - _DEFAULT_SOFT_LIMIT)
    return soft, hard


def _describe_tools(tool_names: Iterable[str]) -> str:
    names = [str(n) for n in dict.fromkeys(tool_names) if n]
    if not names:
        return "the same tool call"
    if len(names) == 1:
        return f"`{names[0]}`"
    shown = ", ".join(f"`{n}`" for n in names[:3])
    if len(names) > 3:
        shown += ", …"
    return shown


def build_stagnation_nudge(run_length: int, tool_names: Iterable[str]) -> str:
    """One-shot message injected when a call repeats to the soft limit."""
    what = _describe_tools(tool_names)
    return (
        f"[System: You have now called {what} with identical arguments "
        f"{run_length} times in a row. The inputs have not changed, so the "
        "result will not change either — repeating it makes no progress. Do "
        "NOT issue the same call again. Either take a different action (change "
        "the arguments, use a different tool, or address the underlying "
        "problem another way), or, if you have everything you need, stop and "
        "give your final answer.]"
    )


def build_stagnation_halt_message(run_length: int, tool_names: Iterable[str]) -> str:
    """Final message when a call repeats to the hard limit and the loop stops."""
    what = _describe_tools(tool_names)
    return (
        f"I stopped because I was repeating the same action — {what} with the "
        f"same arguments — {run_length} times without making progress, and the "
        "result was not going to change. Here is where things stand and what I "
        "was unable to get past:\n\n"
        "- The repeated step did not move the task forward.\n"
        "- Continuing would only have burned more time on an identical result.\n\n"
        "If you can give me a different angle, more detail, or a correction to "
        "the assumption I was stuck on, I'll pick it up from there."
    )


__all__ = [
    "tool_calls_fingerprint",
    "stagnation_guard_enabled",
    "stagnation_limits",
    "build_stagnation_nudge",
    "build_stagnation_halt_message",
]
