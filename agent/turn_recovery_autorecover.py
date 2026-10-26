"""Bounded post-exhaustion auto-recovery ladder for a pre-delivery turn.

Runs once ``api_max_retries`` is spent AND the fallback chain has nothing left
to move to (fallback stays first). While the provider is only *temporarily*
away (5xx, overloaded/529, connect/read timeouts) and no answer text has
reached the user yet, the turn waits with a visible notice instead of ending in
"API failed after N retries", then re-enters the ordinary retry loop.

Cycles: ``agent.auto_recovery_cycles`` (default 5, 0 disables) on a jittered
15/30/60/60/60 s schedule; a provider ``Retry-After`` wins up to 120 s.
Deterministic failures (auth, format, billing, policy, overflow, ...) never
enter, and an interrupt cancels the wait cleanly.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from agent.error_classifier import FailoverReason

logger = logging.getLogger(__name__)

DEFAULT_AUTO_RECOVERY_CYCLES = 5

# Transient transport verdicts: the provider is expected back.
_LADDER_REASONS = frozenset({
    FailoverReason.overloaded,
    FailoverReason.server_error,
    FailoverReason.timeout,
})

_LADDER_BASE_DELAY_S = 15.0
_LADDER_CAP_S = 60.0
# A provider that names its own cooldown knows better than the schedule, within reason.
_RETRY_AFTER_CAP_S = 120.0

# How the user stops the wait on each surface.
_STOP_HINTS = {
    "cli": "press Esc to stop",
    "tui": "press Esc to stop",
    "desktop": "press Esc to stop",
    "api_server": "cancel the request to stop",
    "cron": "",
}
_DEFAULT_STOP_HINT = "send /stop to cancel"


def auto_recovery_cycles(agent: Any) -> int:
    """Configured ``agent.auto_recovery_cycles`` (0 disables the ladder)."""
    try:
        return max(int(getattr(agent, "_auto_recovery_cycles", 0) or 0), 0)
    except (TypeError, ValueError):
        return 0


def _retry_after_seconds(api_error: Any) -> Optional[float]:
    """Provider-declared cooldown from a ``Retry-After`` header, if numeric."""
    headers = getattr(getattr(api_error, "response", None), "headers", None)
    raw = None
    if headers is not None:
        try:
            raw = headers.get("retry-after") or headers.get("Retry-After")
        except Exception:
            raw = None
    try:
        value = float(raw) if raw is not None else None
    except (TypeError, ValueError):
        value = None
    return value if value is not None and value > 0 else None


def ladder_wait_seconds(cycle: int, api_error: Any) -> float:
    """Wait before recovery ``cycle`` (1-based): jittered 15/30/60/60/60 s, or
    the provider's ``Retry-After`` (honoured past the 60 s cap, up to 120 s)."""
    from agent.retry_utils import jittered_backoff

    retry_after = _retry_after_seconds(api_error)
    if retry_after is not None:
        return min(retry_after, _RETRY_AFTER_CAP_S)
    return jittered_backoff(
        cycle,
        base_delay=_LADDER_BASE_DELAY_S,
        max_delay=_LADDER_CAP_S,
        jitter_ratio=0.2,
    )


def ladder_eligible(agent: Any, classified: Any) -> bool:
    """True when cycles are configured, the failure is a transient transport
    verdict, and no answer text has been streamed to the user yet (delivered
    text is never replayed by this path)."""
    if auto_recovery_cycles(agent) <= 0:
        return False
    if getattr(classified, "reason", None) not in _LADDER_REASONS:
        return False
    streamed = getattr(agent, "_current_streamed_assistant_text", "") or ""
    has_content = getattr(agent, "_has_content_after_think_block", None)
    if callable(has_content):
        return not has_content(streamed)
    return not streamed.strip()


def ladder_notice(agent: Any, *, wait_s: float, cycle: int, total: int) -> str:
    platform = str(getattr(agent, "platform", "") or "").lower()
    hint = _STOP_HINTS.get(platform, _DEFAULT_STOP_HINT)
    text = (
        f"⏳ Provider temporarily unavailable — retrying automatically in "
        f"{wait_s:.0f}s (cycle {cycle}/{total})"
    )
    return f"{text}; {hint}" if hint else text


def next_recovery_wait(
    agent: Any, api_error: Any, classified: Any, retry_state: Any
) -> Optional[float]:
    """Claim the next recovery cycle and announce it. Returns the wait in
    seconds, or ``None`` when the ladder does not apply or is spent."""
    if not ladder_eligible(agent, classified):
        return None
    total = auto_recovery_cycles(agent)
    used = int(getattr(retry_state, "auto_recovery_cycles_used", 0) or 0)
    if used >= total:
        agent._emit_status(
            f"⏳ Automatic recovery gave up after {total} cycles — the provider is "
            "still unavailable."
        )
        return None
    cycle = used + 1
    retry_state.auto_recovery_cycles_used = cycle
    wait_s = ladder_wait_seconds(cycle, api_error)
    agent._emit_status(ladder_notice(agent, wait_s=wait_s, cycle=cycle, total=total))
    logger.warning(
        "%sProvider unavailable (%s) — auto-recovery cycle %d/%d, retrying in %.0fs",
        getattr(agent, "log_prefix", ""),
        classified.reason.value,
        cycle,
        total,
        wait_s,
    )
    return wait_s


def wait_interruptibly(agent: Any, wait_s: float, label: str) -> bool:
    """Sleep ``wait_s`` in 200 ms slices. Returns True if interrupted."""
    end = time.time() + wait_s
    ticks = 0
    while time.time() < end:
        if getattr(agent, "_interrupt_requested", False):
            return True
        time.sleep(0.2)
        ticks += 1
        if ticks % 150 == 0:  # ~30 s: keep the gateway inactivity monitor fed
            touch = getattr(agent, "_touch_activity", None)
            if callable(touch):
                touch(f"{label}, {int(end - time.time())}s remaining")
    return False


def interrupted_result(
    agent: Any,
    messages: Any,
    conversation_history: Any,
    api_call_count: int,
    cycle_label: str,
) -> Dict[str, Any]:
    """Turn result for an interrupt during the recovery wait."""
    from agent.message_sanitization import close_interrupted_tool_sequence

    agent._vprint(
        f"{agent.log_prefix}⚡ Interrupt detected during automatic recovery wait, aborting.",
        force=True,
    )
    text = (
        f"Operation interrupted: waiting for the provider to recover ({cycle_label})."
    )
    close_interrupted_tool_sequence(messages, text)
    agent._persist_session(messages, conversation_history)
    agent.clear_interrupt()
    return {
        "final_response": text,
        "messages": messages,
        "api_calls": api_call_count,
        "completed": False,
        "interrupted": True,
    }
