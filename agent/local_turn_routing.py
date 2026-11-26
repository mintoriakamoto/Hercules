"""Send simple turns to a local model (Ollama, LM Studio, llama.cpp …).

Opt-in via ``agent.local_routing`` in ``config.yaml``::

    agent:
      local_routing:
        enabled: true
        model: qwen3:8b
        base_url: http://localhost:11434/v1   # Ollama's OpenAI-compatible API

How a turn is judged
--------------------
At the top of every user turn (after the previous turn's runtime has been
restored) the user's message is scored by the existing task router,
``agent.task_aware_model_router``.  The turn goes to the local model only when
*all* of these hold:

1. the message is plain text, at most ``max_message_chars`` long, with no code
   fence;
2. the router scores it ``simple`` *and* picks its ``fast_cheap`` tier (so the
   router's security and complex-reasoning rules keep a turn on the primary);
3. the whole request (system prompt + history + tool schemas) is estimated to
   fit in ``max_request_tokens``;
4. the endpoint is on this machine or the local network (unless
   ``allow_non_local_endpoint`` is set);
5. the endpoint answers and serves the configured model.

Anything else stays on the configured (primary) model.  The routing is
turn-scoped: the next turn always starts back on the primary.

What it never does silently
---------------------------
* It never sends a turn to a *hosted* model the user did not configure: the
  only two runtimes in play are the local one above and the primary.
* If the local model fails mid-turn, the turn does **not** move to the primary
  or to ``fallback_providers`` unless ``fallback_to_primary: true``.  The error
  is shown instead, with the switch that changes it.
* Every routed turn is announced (``announce``, default on) and logged at
  INFO with the reason, so it is always visible which model answered.
"""

from __future__ import annotations

import ipaddress
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# The main agent carries dozens of tools, and the router's complexity heuristic
# treats >10 tools as a "complex" signal (and <=2 as "simple").  At turn level
# the toolbox is the same for every message, so it says nothing about *this*
# message; a value inside the neutral band keeps the score about the text.
_NEUTRAL_TOOL_COUNT = 5

_PROBE_OK_TTL_S = 30.0
_PROBE_FAIL_TTL_S = 10.0
_LOCAL_HOST_SUFFIXES = (".localhost", ".local", ".lan", ".internal", ".home.arpa")


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off", ""}:
        return False
    return default


def _as_int(value: Any, default: int, *, minimum: int = 1) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number if number >= minimum else default


@dataclass(frozen=True)
class LocalRoutingConfig:
    """Parsed ``agent.local_routing`` section."""

    enabled: bool = False
    model: str = ""
    base_url: str = "http://localhost:11434/v1"
    # Sent as the bearer token.  Explicit so the custom-provider resolver never
    # reaches for OPENAI_API_KEY and sends a hosted key to this endpoint.
    api_key: str = "ollama"
    max_message_chars: int = 400
    max_request_tokens: int = 24000
    fallback_to_primary: bool = False
    allow_non_local_endpoint: bool = False
    health_check: bool = True
    announce: bool = True

    @classmethod
    def from_config(cls, section: Any) -> "LocalRoutingConfig":
        if not isinstance(section, dict):
            return cls()
        defaults = cls()
        return cls(
            enabled=_as_bool(section.get("enabled"), False),
            model=str(section.get("model") or "").strip(),
            base_url=str(section.get("base_url") or defaults.base_url).strip(),
            api_key=str(section.get("api_key") or defaults.api_key).strip(),
            max_message_chars=_as_int(
                section.get("max_message_chars"), defaults.max_message_chars
            ),
            max_request_tokens=_as_int(
                section.get("max_request_tokens"), defaults.max_request_tokens
            ),
            fallback_to_primary=_as_bool(section.get("fallback_to_primary"), False),
            allow_non_local_endpoint=_as_bool(
                section.get("allow_non_local_endpoint"), False
            ),
            health_check=_as_bool(section.get("health_check"), True),
            announce=_as_bool(section.get("announce"), True),
        )

    @property
    def usable(self) -> bool:
        return self.enabled and bool(self.model) and bool(self.base_url)


@dataclass
class TurnRoute:
    """Where one turn runs, and why."""

    local: bool
    reason: str
    model: str = ""
    base_url: str = ""
    complexity: str = ""
    tier: str = ""


# ── Endpoint checks ─────────────────────────────────────────────────────────


def is_local_endpoint(base_url: str) -> bool:
    """True for loopback, private-network and ``.local``-style hosts."""
    try:
        host = (urlparse(base_url).hostname or "").strip().lower()
    except ValueError:
        return False
    if not host:
        return False
    if host == "localhost" or host.endswith(_LOCAL_HOST_SUFFIXES):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private or ip.is_link_local


_probe_cache: Dict[Tuple[str, str], Tuple[float, Optional[str]]] = {}
_probe_lock = threading.Lock()


def _model_names_match(wanted: str, served: str) -> bool:
    if wanted == served:
        return True
    # Ollama lists ``name:latest`` for a model pulled without a tag.
    return f"{wanted}:latest" == served or wanted == f"{served}:latest"


def probe_local_endpoint(
    base_url: str, model: str, api_key: str = "", *, timeout: float = 1.5
) -> Optional[str]:
    """Return ``None`` when ``model`` is served at ``base_url``, else a reason.

    Uses the OpenAI-compatible ``GET /models`` that Ollama, LM Studio, llama.cpp
    and vLLM all expose.  Results are cached briefly so a chat does not pay a
    round trip on every message.
    """
    key = (base_url.rstrip("/"), model)
    now = time.monotonic()
    with _probe_lock:
        cached = _probe_cache.get(key)
        if cached and cached[0] > now:
            return cached[1]

    reason: Optional[str]
    try:
        import requests

        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        resp = requests.get(f"{key[0]}/models", headers=headers, timeout=timeout)
        if resp.status_code != 200:
            reason = f"endpoint answered HTTP {resp.status_code}"
        else:
            served = [
                str(item.get("id") or "")
                for item in (resp.json() or {}).get("data", [])
                if isinstance(item, dict)
            ]
            if any(_model_names_match(model, name) for name in served):
                reason = None
            else:
                reason = (
                    f"model {model!r} is not served there"
                    f" (for Ollama: `ollama pull {model}`)"
                )
    except Exception as exc:  # connection refused, timeout, bad JSON
        reason = f"endpoint not reachable ({type(exc).__name__})"

    ttl = _PROBE_OK_TTL_S if reason is None else _PROBE_FAIL_TTL_S
    with _probe_lock:
        _probe_cache[key] = (now + ttl, reason)
    return reason


def clear_probe_cache() -> None:
    with _probe_lock:
        _probe_cache.clear()


# ── The decision (pure, no agent state) ─────────────────────────────────────


def decide_turn_route(
    message: Any,
    cfg: LocalRoutingConfig,
    *,
    request_tokens: int,
    probe: Callable[..., Optional[str]] = probe_local_endpoint,
) -> TurnRoute:
    """Decide whether one user turn runs on the local model."""
    if not cfg.enabled:
        return TurnRoute(False, "local routing is off")
    if not cfg.model:
        return TurnRoute(False, "agent.local_routing.model is not set")
    if not isinstance(message, str):
        return TurnRoute(False, "message is not plain text")
    text = message.strip()
    if not text:
        return TurnRoute(False, "empty message")
    if len(text) > cfg.max_message_chars:
        return TurnRoute(
            False, f"message longer than {cfg.max_message_chars} characters"
        )
    if "```" in text:
        return TurnRoute(False, "message contains a code block")

    from agent.extended_reasoning import ReasoningComplexity
    from agent.routing_security import RoutingSecurityValidator
    from agent.routing_types import ModelTier
    from agent.task_aware_model_router import get_model_router

    if not RoutingSecurityValidator.validate_task_description(text):
        return TurnRoute(False, "router rejected the message")
    try:
        decision = get_model_router().analyze_task(
            text, available_tools=_NEUTRAL_TOOL_COUNT
        )
    except Exception as exc:
        return TurnRoute(False, f"router failed ({type(exc).__name__})")

    complexity = decision.complexity.value
    tier = decision.recommended_tier.value
    if (
        decision.complexity != ReasoningComplexity.SIMPLE
        or decision.recommended_tier != ModelTier.FAST_CHEAP
    ):
        return TurnRoute(
            False,
            f"router scored it {complexity}/{tier}",
            complexity=complexity,
            tier=tier,
        )

    if request_tokens > cfg.max_request_tokens:
        return TurnRoute(
            False,
            f"request ~{request_tokens} tokens is over max_request_tokens "
            f"({cfg.max_request_tokens})",
            complexity=complexity,
            tier=tier,
        )

    if not cfg.allow_non_local_endpoint and not is_local_endpoint(cfg.base_url):
        return TurnRoute(
            False,
            f"{cfg.base_url} is not a local address "
            "(set allow_non_local_endpoint to use it)",
            complexity=complexity,
            tier=tier,
        )

    if cfg.health_check:
        problem = probe(cfg.base_url, cfg.model, cfg.api_key)
        if problem:
            return TurnRoute(
                False,
                f"local model unavailable: {problem}",
                complexity=complexity,
                tier=tier,
            )

    return TurnRoute(
        True,
        "simple step",
        model=cfg.model,
        base_url=cfg.base_url,
        complexity=complexity,
        tier=tier,
    )


# ── Applying it to an agent ─────────────────────────────────────────────────


def local_route_active(agent) -> bool:
    return getattr(agent, "_turn_route_state", None) is not None


def _activate_local_runtime(agent, cfg: LocalRoutingConfig) -> bool:
    """Swap ``agent`` onto the local endpoint for the rest of this turn.

    Marks the swap the same way a fallback does (``_fallback_activated``), so
    the next turn's ``restore_primary_runtime`` brings the primary back.  The
    primary credential pool is stashed so restore can re-attach it.
    """
    from agent.auxiliary_client import resolve_provider_client
    from agent.chat_completion_helpers import (
        _reset_stale_streak,
        rewrite_prompt_model_identity,
    )

    client, _ = resolve_provider_client(
        "custom",
        model=cfg.model,
        raw_codex=True,
        explicit_base_url=cfg.base_url,
        explicit_api_key=cfg.api_key,
    )
    if client is None:
        return False

    agent._turn_route_state = {
        "credential_pool": getattr(agent, "_credential_pool", None),
        "primary_model": agent.model,
        "primary_provider": agent.provider,
        "local_model": cfg.model,
    }
    base_url = str(client.base_url)
    agent.model = cfg.model
    agent.provider = "custom"
    agent.base_url = base_url
    agent.api_mode = "chat_completions"
    if hasattr(agent, "_transport_cache"):
        agent._transport_cache.clear()
    agent.api_key = client.api_key
    agent.client = client
    agent._client_kwargs = {"api_key": client.api_key, "base_url": base_url}
    # The primary's pool must not rotate keys against the local endpoint.
    agent._credential_pool = None
    agent._use_prompt_caching, agent._use_native_cache_layout = (
        agent._anthropic_prompt_cache_policy(
            provider="custom",
            base_url=base_url,
            api_mode="chat_completions",
            model=cfg.model,
        )
    )
    rewrite_prompt_model_identity(agent, cfg.model, "custom")
    _reset_stale_streak(agent)
    agent._fallback_activated = True
    return True


def apply_turn_route(
    agent,
    user_message: Any,
    messages: List[Dict[str, Any]],
    system_prompt: Optional[str],
) -> TurnRoute:
    """Decide and, when local, switch ``agent`` for this turn. Never raises."""
    cfg: LocalRoutingConfig = getattr(agent, "_local_routing_config", None) or (
        LocalRoutingConfig()
    )
    agent._turn_route = None
    if not cfg.usable:
        return TurnRoute(False, "local routing is off")
    if getattr(agent, "_delegate_depth", 0):
        # Delegated children have their own router (delegation.enable_task_routing).
        return TurnRoute(False, "delegated child")
    if getattr(agent, "_fallback_activated", False):
        # The primary is still cooling down from a rate limit; leave it alone.
        return TurnRoute(False, "a fallback provider is active this turn")

    try:
        from agent.model_metadata import estimate_request_tokens_rough

        tokens = estimate_request_tokens_rough(
            messages,
            system_prompt=system_prompt or "",
            tools=getattr(agent, "tools", None) or None,
        )
        route = decide_turn_route(user_message, cfg, request_tokens=tokens)
    except Exception as exc:
        logger.warning("Local routing check failed; staying on primary: %s", exc)
        return TurnRoute(False, f"routing check failed ({type(exc).__name__})")

    primary = f"{agent.model} via {agent.provider}"
    if not route.local:
        logger.info("Turn routing: primary %s (%s)", primary, route.reason)
        agent._turn_route = route
        return route

    try:
        activated = _activate_local_runtime(agent, cfg)
    except Exception as exc:
        activated = False
        logger.warning("Could not switch to local model %s: %s", cfg.model, exc)
        if local_route_active(agent):
            agent._restore_primary_runtime()
    if not activated:
        route = TurnRoute(
            False,
            "could not build a client for the local endpoint",
            complexity=route.complexity,
            tier=route.tier,
        )
        logger.info("Turn routing: primary %s (%s)", primary, route.reason)
        agent._turn_route = route
        return route

    agent._turn_route = route
    logger.info(
        "Turn routing: local %s at %s (simple step, router %s/%s; primary %s)",
        cfg.model,
        cfg.base_url,
        route.complexity,
        route.tier,
        primary,
    )
    if cfg.announce:
        agent._emit_status(f"🏠 Simple step → local model {cfg.model}")
    return route


def handle_local_route_failure(agent, reason=None) -> bool:
    """Called instead of the fallback chain while a turn runs on the local model.

    Returns True when the caller should retry (back on the primary), False to
    surface the error.
    """
    cfg: LocalRoutingConfig = getattr(agent, "_local_routing_config", None) or (
        LocalRoutingConfig()
    )
    state = getattr(agent, "_turn_route_state", None) or {}
    local_model = state.get("local_model") or agent.model
    primary_model = state.get("primary_model") or "the primary model"
    why = getattr(reason, "value", reason) or "error"
    if not cfg.fallback_to_primary:
        logger.warning(
            "Local model %s failed (%s); not retrying on %s because "
            "agent.local_routing.fallback_to_primary is off",
            local_model,
            why,
            primary_model,
        )
        agent._emit_warning(
            f"Local model {local_model} failed ({why}). Not retrying on "
            f"{primary_model}: set agent.local_routing.fallback_to_primary: true "
            "to allow that, or check that Ollama is running."
        )
        return False
    restored = agent._restore_primary_runtime()
    if restored:
        logger.info(
            "Local model %s failed (%s); retrying this turn on primary %s "
            "(fallback_to_primary is on)",
            local_model,
            why,
            agent.model,
        )
        agent._emit_status(
            f"🏠 Local model {local_model} failed, so this step is retrying on "
            f"{agent.model}"
        )
    return restored
