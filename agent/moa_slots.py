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

This module closes that gap by resolving each slot against real credential
state before the call: a slot whose provider is not authenticated is realigned
onto the provider/model the session is actually running, so a fan-out degrades
to "several passes on the model I have" instead of failing wholesale. Slots
whose provider *is* authenticated are returned untouched, so a genuinely
multi-provider install keeps its configured diversity.

Nothing here raises: every helper degrades to "assume available / leave the
slot alone", which reproduces the pre-alignment behaviour.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Providers that serve a local inference server and need no credentials. An
# auth-store lookup reports them as unconfigured, which would realign a
# deliberately-local advisor onto a cloud model — exactly backwards for a
# user who picked a local provider on purpose.
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
    "text-generation-webui",
})

# The MoA virtual provider is never a valid fallback target: using it as one
# would re-enter the preset that is currently being resolved.
_VIRTUAL_PROVIDERS = frozenset({"moa"})

# Credential state changes only on login/logout, but a MoA turn resolves slots
# on every tool-loop iteration. Cache the per-provider answer briefly so a
# fan-out does not re-read the auth store once per advisor per iteration.
_AVAILABILITY_TTL_SECONDS = 30.0
_availability_cache: dict[str, tuple[float, bool]] = {}
_availability_lock = threading.Lock()


def clear_availability_cache() -> None:
    """Drop memoized credential answers (login/logout, and tests)."""
    with _availability_lock:
        _availability_cache.clear()


def _normalize(provider: Any) -> str:
    return str(provider or "").strip().lower()


def _probe_provider(provider: str) -> bool:
    """Uncached credential probe for one provider slug."""
    if not provider or provider in _VIRTUAL_PROVIDERS:
        return False
    if provider in _LOCAL_PROVIDERS:
        return True
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


def provider_is_available(provider: Any) -> bool:
    """Return True when *provider* has usable credentials right now.

    Fails OPEN (True) on any lookup error: a broken probe must never strip a
    working advisor out of a preset.
    """
    slug = _normalize(provider)
    if not slug:
        return False
    now = time.monotonic()
    with _availability_lock:
        hit = _availability_cache.get(slug)
        if hit is not None and (now - hit[0]) < _AVAILABILITY_TTL_SECONDS:
            return hit[1]
    try:
        available = _probe_provider(slug)
    except Exception as exc:  # pragma: no cover - probe must never decide by crashing
        logger.debug("MoA credential probe failed for %s: %s", slug, exc)
        available = True
    with _availability_lock:
        _availability_cache[slug] = (time.monotonic(), available)
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
    except Exception:  # pragma: no cover - config read failure
        return None

    if not provider or provider in _VIRTUAL_PROVIDERS or provider == "auto":
        # A session parked on a MoA preset records provider "moa" and, as its
        # model, the PRESET NAME — never a model any backend can serve. Drop
        # the model with the virtual provider and re-derive both from the auth
        # store, or the fallback would be as unrunnable as the slot it
        # replaces.
        if provider in _VIRTUAL_PROVIDERS:
            model = ""
        try:
            from hercules_cli.auth import get_active_provider

            provider = _normalize(get_active_provider())
        except Exception:
            provider = ""
    if not provider or provider in _VIRTUAL_PROVIDERS:
        return None
    if not provider_is_available(provider):
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
    if provider and model and provider_is_available(provider):
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
