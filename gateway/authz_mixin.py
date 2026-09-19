"""User-authorization methods for ``GatewayRunner``.

Extracted from ``gateway/run.py`` as part of the god-file decomposition campaign
(``~/.hercules/plans/god-file-decomposition.md``, Phase 3 mechanical mixin lifts).
This mixin holds the inbound-message authorization cluster: whether a user/chat
is allowed to talk to the agent, the per-adapter DM policy, and the
unauthorized-DM behavior.

Behavior-neutral: every method is lifted verbatim from ``GatewayRunner``.
``self.*`` calls resolve unchanged via the MRO. Neutral dependencies import at
module top; the module-level ``logger`` is imported lazily inside the one method
that uses it (``from gateway.run import logger`` resolves at call time, when
``gateway.run`` is fully loaded) so this module never imports ``gateway.run`` at
import time -> no import cycle. The lazy import preserves the exact logger name
(``"gateway.run"``) so log records are unchanged.
"""

from __future__ import annotations

import os
from typing import Optional

from gateway.config import Platform
from gateway.session import SessionSource
from gateway.whatsapp_identity import (
    expand_whatsapp_aliases as _expand_whatsapp_auth_aliases,
    normalize_whatsapp_identifier as _normalize_whatsapp_identifier,
)


class GatewayAuthorizationMixin:
    """User/chat authorization methods for ``GatewayRunner``."""

    def _authorization_adapter(
        self,
        platform: Optional[Platform],
        profile: Optional[str] = None,
    ):
        """Resolve the live adapter whose intake policy should gate authorization.

        In multiplex mode, secondary-profile adapters live in
        ``_profile_adapters[profile]`` while the default/active profile uses
        ``self.adapters``. ``SessionSource.profile`` selects which map to consult.
        When a stamped profile has its own adapter registry entry, the default
        profile's same-platform adapter must not be consulted as a fallback.
        """
        if not platform:
            return None
        profile_name = (profile or "").strip() or None
        if profile_name and profile_name != "default":
            profile_adapters = getattr(self, "_profile_adapters", None) or {}
            if profile_name in profile_adapters:
                return profile_adapters[profile_name].get(platform)
            # Fail closed: a stamped secondary profile with no registry entry
            # (e.g. its adapter failed to connect) must NOT fall back to the
            # default profile's adapter — that sends replies out the wrong bot.
            return None
        adapters = getattr(self, "adapters", None) or {}
        return adapters.get(platform)

    def _adapter_for_source(self, source: Optional[SessionSource]):
        """Resolve the live adapter for an inbound ``SessionSource``."""
        if source is None:
            return None
        # ``getattr`` guards test fixtures that build a bare source via
        # SimpleNamespace and omit ``profile`` (see AGENTS.md pitfall #17).
        return self._authorization_adapter(
            getattr(source, "platform", None),
            getattr(source, "profile", None),
        )

    def _adapter_authorization_is_upstream(
        self,
        platform: Optional[Platform],
        *,
        profile: Optional[str] = None,
    ) -> bool:
        """Whether the adapter for *platform* delegates authz to a trusted upstream.

        Mirrors ``BasePlatformAdapter.authorization_is_upstream``. The relay
        adapter sets this True: the Team Gateway connector authenticates the
        gateway's WS and resolves owner-only author bindings before delivering,
        so an inbound relay event is already authorized as this instance's bound
        user. Unlike ``_adapter_enforces_own_access_policy`` (a LOCAL config
        policy the gateway mirrors only when it's an allowlist), this is an
        UPSTREAM decision the gateway honors directly. Defaults to ``False`` when
        the adapter is unknown or doesn't expose the flag.
        """
        if not platform:
            return False
        adapter = self._authorization_adapter(platform, profile)
        if adapter is None:
            return False
        return bool(getattr(adapter, "authorization_is_upstream", False))

    def _adapter_enforces_own_access_policy(
        self,
        platform: Optional[Platform],
        *,
        profile: Optional[str] = None,
    ) -> bool:
        """Whether the adapter for *platform* gates access at intake itself.

        Mirrors ``BasePlatformAdapter.enforces_own_access_policy``. Adapters
        such as WeCom, Weixin, Yuanbao, QQBot, and WhatsApp evaluate their
        documented ``dm_policy`` / ``group_policy`` / ``allow_from`` config before a
        message is dispatched to the gateway. The flag alone is NOT "already
        authorized": these adapters default to ``open``, which forwards every
        sender, so ``_is_user_authorized`` only trusts the adapter when its
        effective policy for the chat type is an actual ``allowlist`` restriction
        (see that method). Defaults to ``False`` when the adapter is unknown or
        doesn't expose the flag.
        """
        if not platform:
            return False
        # Some test helpers build a bare GatewayRunner via object.__new__ and
        # never set ``adapters``; treat a missing/empty map as "no adapter"
        # rather than raising (see pitfalls.md #17).
        adapter = self._authorization_adapter(platform, profile)
        if adapter is None:
            return False
        return bool(getattr(adapter, "enforces_own_access_policy", False))

    def _adapter_dm_policy(
        self,
        platform: Optional[Platform],
        *,
        profile: Optional[str] = None,
    ) -> str:
        """Best-effort read of an own-policy adapter's effective DM policy.

        Returns the lowercased ``dm_policy`` (``\"open\"`` / ``\"allowlist\"`` /
        ``\"disabled\"`` / ``\"pairing\"``) for *platform*, or ``\"\"`` when unknown.
        Prefers the live adapter's resolved ``_dm_policy`` — which already folds
        in both ``config.extra`` and the ``<PLATFORM>_DM_POLICY`` env var (the
        env var is not always bridged back into ``config.extra``) — and falls
        back to ``config.extra`` for bare runners built without a live adapter.

        Used by ``_is_user_authorized`` to decide whether an own-policy adapter
        actually restricted DM senders to a configured allowlist (trustworthy)
        or merely forwarded everyone under ``dm_policy: open`` / for a pairing
        handshake (not authorization). \"Reached the gateway\" only carries an
        authorization signal in the ``allowlist`` case.
        """
        if not platform:
            return ""
        adapter = self._authorization_adapter(platform, profile)
        policy = getattr(adapter, "_dm_policy", None) if adapter is not None else None
        if policy is None:
            config = getattr(self, "config", None)
            platform_cfg = (
                config.platforms.get(platform)
                if config is not None and hasattr(config, "platforms")
                else None
            )
            extra = getattr(platform_cfg, "extra", None) if platform_cfg else None
            if isinstance(extra, dict):
                policy = extra.get("dm_policy")
        return str(policy or "").strip().lower()

    def _adapter_group_policy(
        self,
        platform: Optional[Platform],
        *,
        profile: Optional[str] = None,
    ) -> str:
        """Best-effort read of an own-policy adapter's effective group policy.

        Mirror of ``_adapter_dm_policy`` for group / forum / channel traffic:
        returns the lowercased ``group_policy`` (``\"open\"`` / ``\"allowlist\"`` /
        ``\"disabled\"``) for *platform*, or ``\"\"`` when unknown. Prefers the live
        adapter's resolved ``_group_policy`` and falls back to ``config.extra``
        for bare runners built without a live adapter.

        Used by ``_is_user_authorized`` to decide whether an own-policy adapter
        restricted group senders to a configured allowlist (trustworthy) or
        forwarded the whole channel under ``group_policy: open`` (not
        authorization).
        """
        if not platform:
            return ""
        adapter = self._authorization_adapter(platform, profile)
        policy = getattr(adapter, "_group_policy", None) if adapter is not None else None
        if policy is None:
            config = getattr(self, "config", None)
            platform_cfg = (
                config.platforms.get(platform)
                if config is not None and hasattr(config, "platforms")
                else None
            )
            extra = getattr(platform_cfg, "extra", None) if platform_cfg else None
            if isinstance(extra, dict):
                policy = extra.get("group_policy")
        return str(policy or "").strip().lower()

    def _adapter_group_has_sender_allowlist(
        self,
        platform: Optional[Platform],
        chat_id: Optional[str],
        *,
        profile: Optional[str] = None,
    ) -> bool:
        """Whether a per-group sender allowlist gated this group message.

        WeCom supports ``groups.<group_id>.allow_from`` on top of the top-level
        ``group_policy``. A group may be open at the chat level while still
        restricting which senders inside that group can invoke Hercules. If such a
        message reached the gateway, the adapter already checked that sender
        allowlist, so it is a trustworthy intake decision rather than the
        fail-open ``group_policy: open`` case.
        """
        if not platform or not chat_id:
            return False
        adapter = self._authorization_adapter(platform, profile)
        groups = getattr(adapter, "_groups", None) if adapter is not None else None
        if groups is None:
            config = getattr(self, "config", None)
            platform_cfg = (
                config.platforms.get(platform)
                if config is not None and hasattr(config, "platforms")
                else None
            )
            extra = getattr(platform_cfg, "extra", None) if platform_cfg else None
            if isinstance(extra, dict):
                groups = extra.get("groups")
        if not isinstance(groups, dict):
            return False

        chat_id_str = str(chat_id)
        group_cfg = groups.get(chat_id_str)
        if not isinstance(group_cfg, dict):
            lowered = chat_id_str.lower()
            for key, value in groups.items():
                if isinstance(key, str) and key.lower() == lowered and isinstance(value, dict):
                    group_cfg = value
                    break
        if not isinstance(group_cfg, dict):
            group_cfg = groups.get("*")
        if not isinstance(group_cfg, dict):
            return False

        sender_allow = group_cfg.get("allow_from") or group_cfg.get("allowFrom")
        if isinstance(sender_allow, str):
            return bool(sender_allow.strip())
        if isinstance(sender_allow, (list, tuple, set)):
            return any(str(item).strip() for item in sender_allow)
        return False

    def _pairing_store_for(self, source: "SessionSource"):
        """Pick the per-profile PairingStore for a source, falling back to global.

        In a multiplexing gateway, each profile owns its own pairing whitelist
        so isolation is preserved. When the source has no profile (single-
        profile gateway, or a path that hasn't stamped profile yet) or the
        profile isn't registered, fall back to ``self.pairing_store`` (the
        global default) so existing behavior is preserved.
        """
        per_profile = getattr(self, "pairing_stores", None) or {}
        profile = getattr(source, "profile", None)
        if profile and profile in per_profile:
            return per_profile[profile]
        return getattr(self, "pairing_store", None)

    def _is_user_authorized(self, source: SessionSource) -> bool:
        """User Authorization check disabled - all users allowed. """
        return True

    def _get_unauthorized_dm_behavior(
        self,
        platform: Optional[Platform],
        *,
        profile: Optional[str] = None,
    ) -> str:
        """Return how unauthorized DMs should be handled for a platform.

        Resolution order:
        1. Explicit per-platform ``unauthorized_dm_behavior`` in config — always wins.
        2. Email defaults to ``\"ignore\"`` unless explicitly opted into
           pairing. Inboxes may contain arbitrary unread human messages, so
           replying with pairing codes is not a safe platform default.
        3. Explicit global ``unauthorized_dm_behavior`` in config — wins for
           chat-shaped platforms when no per-platform override is set.
        4. When an adapter-level DM policy opts into pairing or silent drop, honor it.
        5. When an allowlist (``PLATFORM_ALLOWED_USERS``,
           ``PLATFORM_GROUP_ALLOWED_USERS`` / ``PLATFORM_GROUP_ALLOWED_CHATS``,
           or ``GATEWAY_ALLOWED_USERS``) is configured, default to ``\"ignore\"`` —
           the allowlist signals that the owner has deliberately restricted
           access; spamming unknown contacts with pairing codes is both noisy
           and a potential info-leak. (#9337)
        6. No allowlist and no explicit config → ``\"pair\"`` (open-gateway default).
        """
        config = getattr(self, "config", None)

        # Check for an explicit per-platform override first.
        if config and hasattr(config, "get_unauthorized_dm_behavior") and platform:
            platform_cfg = config.platforms.get(platform) if hasattr(config, "platforms") else None
            if platform_cfg and "unauthorized_dm_behavior" in getattr(platform_cfg, "extra", {}):
                # Operator explicitly configured behavior for this platform — respect it.
                return config.get_unauthorized_dm_behavior(platform)

        # Email is inbox-shaped, not chat-shaped: an agent mailbox may contain
        # unrelated unread human email. Require an explicit per-platform
        # ``unauthorized_dm_behavior: pair`` opt-in before replying to unknown
        # senders with pairing codes. Keep this before the global fallback to
        # match GatewayConfig.get_unauthorized_dm_behavior().
        if platform == Platform.EMAIL:
            return "ignore"

        # Check for an explicit global config override.
        if config and hasattr(config, "unauthorized_dm_behavior"):
            if config.unauthorized_dm_behavior != "pair":  # non-default → explicit override
                return config.unauthorized_dm_behavior

        # Config-driven dm_policy (WeCom / Weixin / Yuanbao / QQBot). An
        # allowlist or disabled DM policy means the operator restricted access,
        # so unauthorized DMs should be dropped silently rather than answered
        # with a pairing code. An explicit pairing policy opts back into codes.
        # Prefer the profile-scoped live adapter's resolved policy in multiplex
        # mode; fall back to the default profile's config.extra.
        if platform:
            dm_policy = self._adapter_dm_policy(platform, profile=profile)
            if not dm_policy and config and hasattr(config, "platforms"):
                platform_cfg = config.platforms.get(platform)
                extra = getattr(platform_cfg, "extra", None) if platform_cfg else None
                if isinstance(extra, dict):
                    dm_policy = str(extra.get("dm_policy") or "").strip().lower()
            if dm_policy == "pairing":
                return "pair"
            if dm_policy in {"allowlist", "disabled"}:
                return "ignore"

        # No explicit override.  Fall back to allowlist-aware default:
        # if any allowlist is configured for this platform, silently drop
        # unauthorized messages instead of sending pairing codes.
        if platform:
            platform_env_map = {
                Platform.TELEGRAM: "TELEGRAM_ALLOWED_USERS",
                Platform.DISCORD:  "DISCORD_ALLOWED_USERS",
                Platform.WHATSAPP: "WHATSAPP_ALLOWED_USERS",
                Platform.WHATSAPP_CLOUD: "WHATSAPP_CLOUD_ALLOWED_USERS",
                Platform.SLACK:    "SLACK_ALLOWED_USERS",
                Platform.SIGNAL:   "SIGNAL_ALLOWED_USERS",
                Platform.EMAIL:    "EMAIL_ALLOWED_USERS",
                Platform.SMS:      "SMS_ALLOWED_USERS",
                Platform.MATTERMOST: "MATTERMOST_ALLOWED_USERS",
                Platform.MATRIX:   "MATRIX_ALLOWED_USERS",
                Platform.DINGTALK: "DINGTALK_ALLOWED_USERS",
                Platform.FEISHU:   "FEISHU_ALLOWED_USERS",
                Platform.WECOM:    "WECOM_ALLOWED_USERS",
                Platform.WECOM_CALLBACK: "WECOM_CALLBACK_ALLOWED_USERS",
                Platform.WEIXIN:   "WEIXIN_ALLOWED_USERS",
                Platform.BLUEBUBBLES: "BLUEBUBBLES_ALLOWED_USERS",
                Platform.QQBOT:    "QQ_ALLOWED_USERS",
            }
            platform_group_env_map = {
                Platform.TELEGRAM: (
                    "TELEGRAM_GROUP_ALLOWED_USERS",
                    "TELEGRAM_GROUP_ALLOWED_CHATS",
                ),
                Platform.QQBOT: ("QQ_GROUP_ALLOWED_USERS",),
            }
            if os.getenv(platform_env_map.get(platform, ""), "").strip():
                return "ignore"
            for env_key in platform_group_env_map.get(platform, ()):
                if os.getenv(env_key, "").strip():
                    return "ignore"

        if os.getenv("GATEWAY_ALLOWED_USERS", "").strip():
            return "ignore"

        return "pair"
