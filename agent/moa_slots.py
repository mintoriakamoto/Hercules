"""Align MoA preset slots with the credentials the session actually has.

A MoA preset pins each advisor / aggregator as a ``{provider, model}`` slot,
and the shipped default preset names three different vendors (OpenAI Codex,
OpenRouter/DeepSeek, OpenRouter/Anthropic). That is a good default only for an
account that is logged into all of them. On a single-provider install — the
common case, e.g. a ChatGPT-OAuth (``openai-codex``) login — the OpenRouter
slots have no credentials, and the damage is worse than a missing key:

``resolve_runtime_provider`` falls back to whatever provider the session *can*
authenticate, while the slot's **model name is carried through unchanged**. The
advisor is then dispatched as ``openai-codex`` + ``anthropic/claude-opus-4.8``
and the Codex backend answers::

    400 {"detail": "The 'anthropic/claude-opus-4.8' model is not supported
     when using Codex with a ChatGPT account."}

— so every advisor in the fan-out fails, and the aggregator (the *acting*
model) fails with it. The preset asked for a model the session was never able
to run.

This module closes that gap by resolving each slot against the real runtime
before the call: a slot the session cannot actually serve is realigned onto
the provider/model it IS running, so a fan-out degrades to "several passes on
the model I have" instead of failing wholesale. Slots the session *can* serve
are returned untouched, so a genuinely multi-provider install keeps its
configured diversity.

The pick is automatic in both directions, decided on the RESOLVED endpoint
rather than on provider names:

* **API session** (the reported case) — slots realign onto the authenticated
  cloud provider's model.
* **Local session** (Ollama, vLLM, llama-server, LM Studio, or ``auto`` plus a
  ``model.base_url`` on a loopback/LAN address) — slots realign onto the local
  model. A local slot needs no credentials, so what decides it is whether the
  server is listening; a dead local port hands the turn back to whatever
  provider is running instead of failing every advisor against it.
* **``providers.local_only``** — a slot that resolves to a cloud endpoint is
  treated as unusable rather than left to raise ``LocalOnlyModeError`` in the
  middle of the fan-out.

Nothing here raises: every helper degrades to "assume available / leave the
slot alone", which reproduces the pre-alignment behaviour.
"""

from __future__ import annotations

import logging
import os
import socket
import threading
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Provider slugs that address a local inference server. This is only a cheap
# pre-check for the no-credentials question: whether a slot is *actually*
# local is decided on its RESOLVED endpoint via runtime_provider's own
# _is_local_endpoint, the same authority local-only mode gates on, so a
# "custom" provider pointed at localhost is recognised and a local-sounding
# alias pointed at a public URL is not.
_LOCAL_PROVIDERS = frozenset({
    "ollama",
    "ollama-local",
    "lmstudio",
    "llamacpp",
    "llama-cpp",
    "vllm",
    "localai",
    "jan",
    "koboldcpp",
    "tabbyapi",
    "exllamav2",
    "text-generation-webui",
})

# The MoA virtual provider is never a valid fallback target: using it as one
# would re-enter the preset that is currently being resolved.
_VIRTUAL_PROVIDERS = frozenset({"moa"})

# Credential state changes only on login/logout, but a MoA turn resolves slots
# on every tool-loop iteration. Cache the per-provider answer briefly so a
# fan-out does not re-read the auth store (or re-probe a local server) once
# per advisor per iteration.
_AVAILABILITY_TTL_SECONDS = 30.0
_availability_cache: dict[tuple[str, str], tuple[float, bool]] = {}
_availability_lock = threading.Lock()

# A local inference server is either listening or it is not — no credential
# tells us. One short TCP connect answers it; anything longer would add
# per-advisor latency to the very turn we are trying to keep working.
_LOCAL_PROBE_TIMEOUT_SECONDS = 0.6


def clear_availability_cache() -> None:
    """Drop memoized credential answers (login/logout, and tests)."""
    with _availability_lock:
        _availability_cache.clear()


def _normalize(provider: Any) -> str:
    return str(provider or "").strip().lower()


def _local_server_is_up(base_url: str) -> bool:
    """True when something is listening at a local endpoint.

    A local slot needs no credentials, so the only question that decides
    whether it can serve this turn is whether the server is running. If it is
    not, the slot must realign onto whatever the session IS using (an API
    provider, typically) rather than fail every advisor against a dead port.
    """
    from urllib.parse import urlparse

    parsed = urlparse((base_url or "").strip())
    host = parsed.hostname
    if not host:
        return False
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=_LOCAL_PROBE_TIMEOUT_SECONDS):
            return True
    except OSError:
        return False


def _credentials_configured(provider: str) -> bool:
    """Auth-store / env-key view of whether *provider* is logged in."""
    if provider == "custom" or provider.startswith("custom:"):
        try:
            from hercules_cli.config import load_config

            model_cfg = load_config().get("model")
            base_url = ""
            if isinstance(model_cfg, dict):
                base_url = str(model_cfg.get("base_url") or "").strip()
            return bool(base_url)
        except Exception:
            return True
    try:
        from hercules_cli.auth import get_auth_status, has_usable_secret
    except Exception:  # pragma: no cover - auth import failure
        return True
    if provider == "openrouter":
        # Mirrors list_available_providers(): OpenRouter is env-key driven and
        # is not represented in the auth store.
        try:
            if has_usable_secret(os.getenv("OPENROUTER_API_KEY", "")):
                return True
        except Exception:
            pass
    try:
        status = get_auth_status(provider) or {}
    except Exception:
        return True
    return bool(status.get("logged_in") or status.get("configured"))


def _probe_provider(provider: str, model: str = "") -> bool:
    """Uncached usability probe for one slot's provider.

    Decided on the RESOLVED endpoint wherever resolution succeeds, because
    that is what the call will actually hit:

    * Local endpoint → usable iff the server is listening. No credentials are
      involved, so liveness is the whole question, and a dead local port must
      hand the turn back to whatever provider IS running.
    * Cloud endpoint under ``providers.local_only`` → unusable. Resolution
      raises ``LocalOnlyModeError`` there anyway; catching it here realigns
      the slot instead of killing the turn mid-fan-out.
    * Resolution landing on a DIFFERENT provider than the one requested →
      unusable. That fallback is precisely the failure this module exists for:
      the endpoint changes, the slot's model name does not, and the call goes
      out as a model the resolved route cannot serve.
    * Otherwise → the auth store / env key decides.
    """
    if not provider or provider in _VIRTUAL_PROVIDERS:
        return False
    try:
        from hercules_cli.runtime_provider import (
            LocalOnlyModeError,
            _is_local_endpoint,
            resolve_runtime_provider,
        )
    except Exception:  # pragma: no cover - resolver import failure
        return provider in _LOCAL_PROVIDERS or _credentials_configured(provider)

    try:
        runtime = resolve_runtime_provider(requested=provider, target_model=model or None)
    except LocalOnlyModeError:
        # Local-only mode is on and this slot is not local. Keeping it would
        # raise the same error mid-turn, on the advisor call.
        return False
    except Exception as exc:
        logger.debug("MoA slot resolution failed for %s: %s", provider, exc)
        return provider in _LOCAL_PROVIDERS or _credentials_configured(provider)

    base_url = str(runtime.get("base_url") or "")
    if base_url and _is_local_endpoint(base_url):
        return _local_server_is_up(base_url)

    resolved = _normalize(runtime.get("provider"))
    if resolved and resolved != provider and provider not in _LOCAL_PROVIDERS:
        # Credentials for the requested provider were not found; resolution
        # silently substituted another route.
        return False

    return _credentials_configured(provider)


def provider_is_available(provider: Any, model: Any = "") -> bool:
    """Return True when this slot's provider can serve the call right now.

    Fails OPEN (True) on any probe error: a broken lookup must never strip a
    working advisor out of a preset.
    """
    slug = _normalize(provider)
    if not slug:
        return False
    key = (slug, str(model or "").strip())
    now = time.monotonic()
    with _availability_lock:
        hit = _availability_cache.get(key)
        if hit is not None and (now - hit[0]) < _AVAILABILITY_TTL_SECONDS:
            return hit[1]
    try:
        available = _probe_provider(key[0], key[1])
    except Exception as exc:  # pragma: no cover - probe must never decide by crashing
        logger.debug("MoA credential probe failed for %s: %s", slug, exc)
        available = True
    with _availability_lock:
        _availability_cache[key] = (time.monotonic(), available)
    return available


def session_slot() -> Optional[dict[str, str]]:
    """The provider/model this session is actually running on.

    Read from ``model.provider`` / ``model.default`` in config.yaml — what
    ``/model`` writes and what the next CLI start would use. The live agent is
    not consulted because on a MoA turn its provider/model *are* the virtual
    preset ("moa" / "<preset name>"), which is never a usable fallback.

    Returns ``None`` when the config names no usable concrete model, or when
    its provider has no credentials either (there is nothing better to offer,
    so callers leave slots alone).
    """
    try:
        from hercules_cli.config import load_config

        config = load_config()
        model_cfg = config.get("model")
        if isinstance(model_cfg, str):
            model_cfg = {"default": model_cfg}
        if not isinstance(model_cfg, dict):
            return None
        provider = _normalize(model_cfg.get("provider"))
        model = str(model_cfg.get("default") or model_cfg.get("model") or "").strip()
        base_url = str(model_cfg.get("base_url") or "").strip()
    except Exception:  # pragma: no cover - config read failure
        return None

    if provider in _VIRTUAL_PROVIDERS:
        # A session parked on a MoA preset records provider "moa" and, as its
        # model, the PRESET NAME — never a model any backend can serve. Drop
        # both, or the fallback would be as unrunnable as the slot it
        # replaces.
        provider = ""
        model = ""

    if provider == "auto" and base_url:
        # "auto" + an explicit base_url is how a local server (Ollama, vLLM,
        # llama-server, LM Studio) is configured. Keep the provider as-is:
        # resolve_runtime_provider resolves "auto" to exactly the route the
        # session is running, so the advisors land on the local model rather
        # than on a cloud account that also happens to be authenticated.
        pass
    elif not provider or provider == "auto":
        try:
            from hercules_cli.auth import get_active_provider

            provider = _normalize(get_active_provider())
        except Exception:
            provider = ""
    if not provider or provider in _VIRTUAL_PROVIDERS:
        return None
    if not provider_is_available(provider, model):
        return None
    if not model:
        # Provider known, model unknown (MoA-parked session, or a provider
        # configured without ever running `hercules model`): take the
        # provider's own cost-safe default rather than giving up.
        try:
            from hercules_cli.models import get_default_model_for_provider

            model = str(get_default_model_for_provider(provider) or "").strip()
        except Exception:
            model = ""
        # A local endpoint serves whatever it has loaded; there is no catalog
        # to take a default from, so an unknown model there means no fallback
        # rather than a guessed slug the server would reject.
    if not model:
        return None
    return {"provider": provider, "model": model}


def align_slot(
    slot: Any,
    fallback: Optional[dict[str, str]],
) -> tuple[dict[str, str], Optional[str]]:
    """Return ``(slot, note)`` with an unusable slot swapped for *fallback*.

    ``note`` is a human-readable description of the substitution, or None when
    the slot was left as configured (the common, fully-credentialed case).
    """
    if not isinstance(slot, dict):
        slot = {}
    provider = _normalize(slot.get("provider"))
    model = str(slot.get("model") or "").strip()
    current = {"provider": provider, "model": model}

    if not fallback:
        return current, None
    fb_provider = _normalize(fallback.get("provider"))
    fb_model = str(fallback.get("model") or "").strip()
    if not fb_provider or not fb_model:
        return current, None
    if provider and model and provider_is_available(provider, model):
        return current, None
    if provider == fb_provider and model == fb_model:
        return current, None

    if not provider or not model:
        reason = "slot is incomplete"
    else:
        reason = f"{provider} is not authenticated"
    note = (
        f"{provider or '<unset>'}:{model or '<unset>'} → "
        f"{fb_provider}:{fb_model} ({reason})"
    )
    return {"provider": fb_provider, "model": fb_model}, note


def align_preset_slots(
    reference_models: Any,
    aggregator: Any,
    fallback: Optional[dict[str, str]] = None,
) -> tuple[list[dict[str, str]], dict[str, str], list[str]]:
    """Align a preset's advisor + aggregator slots to available credentials.

    Advisors that collapse onto a slot another advisor already occupies are
    dropped: running the identical model twice in one fan-out doubles cost and
    latency for advice the aggregator has already seen. The aggregator is never
    dropped — it is the acting model — so a preset whose advisors all collapse
    into the aggregator degrades to a single normal turn plus one advisory
    pass, not to nothing.

    Returns ``(references, aggregator, notes)``.
    """
    if fallback is None:
        fallback = session_slot()

    refs_in = list(reference_models or [])
    aligned_refs: list[dict[str, str]] = []
    notes: list[str] = []
    seen: set[tuple[str, str]] = set()

    for slot in refs_in:
        resolved, note = align_slot(slot, fallback)
        if note:
            notes.append(f"reference {note}")
        key = (resolved.get("provider", ""), resolved.get("model", ""))
        if not key[0] or not key[1]:
            continue
        if key in seen:
            notes.append(
                f"reference {key[0]}:{key[1]} dropped (duplicate after realignment)"
            )
            continue
        seen.add(key)
        aligned_refs.append(resolved)

    aligned_agg, agg_note = align_slot(aggregator, fallback)
    if agg_note:
        notes.append(f"aggregator {agg_note}")

    if notes:
        logger.warning("MoA slots realigned to available credentials: %s", "; ".join(notes))

    return aligned_refs, aligned_agg, notes
