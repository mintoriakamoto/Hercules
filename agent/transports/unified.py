"""Unified transport factory with explicit fallback modes and telemetry.

This module consolidates provider dispatch logic and eliminates silent
fallback bugs by making fallback behavior explicit and observable.

Design:
  - get_transport() never returns None (raises explicit exception)
  - FallbackMode controls migration strategy (feature flags, hard fail, etc.)
  - Telemetry tracks which providers use legacy code paths
  - Progressive migration: new transports roll out per-provider
"""

from __future__ import annotations

import logging
import os
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class FallbackMode(Enum):
    """Controls transport fallback behavior during migration."""
    TRY_LEGACY = "try_legacy"          # Try new, fallback to legacy if needed
    FEATURE_FLAG = "feature_flag"      # Use per-provider feature flag (env var)
    HARD_FAIL = "hard_fail"            # Raise exception, no fallback


class TransportNotAvailable(Exception):
    """Raised when transport is not available and fallback is disabled."""
    def __init__(self, api_mode: str, reason: str = "not implemented"):
        self.api_mode = api_mode
        self.reason = reason
        super().__init__(
            f"Transport not available for '{api_mode}': {reason}"
        )


class TransportFactory:
    """Factory for creating transport instances with explicit fallback handling.

    Features:
      - Per-provider transport resolution
      - Explicit fallback modes (no silent None)
      - Telemetry for migration tracking
      - Feature flag support for gradual rollout
    """

    def __init__(
        self,
        fallback_mode: FallbackMode = FallbackMode.TRY_LEGACY,
        legacy_dispatcher: Optional[callable] = None,
    ):
        """Initialize transport factory.

        Args:
            fallback_mode: How to handle missing transports
            legacy_dispatcher: Callable that provides legacy transport behavior
                              (used in TRY_LEGACY mode)
        """
        self.fallback_mode = fallback_mode
        self.legacy_dispatcher = legacy_dispatcher
        self._fallback_count: dict[str, int] = {}
        self._transport_cache: dict[str, any] = {}

    def get_transport(self, api_mode: str) -> any:
        """Get transport for given API mode.

        Args:
            api_mode: Provider API mode (anthropic, openai, bedrock, etc.)

        Returns:
            Transport instance

        Raises:
            TransportNotAvailable: If no transport available and fallback disabled
        """
        # Try to get new transport
        from agent.transports import get_transport as get_new_transport
        transport = get_new_transport(api_mode)

        if transport is not None:
            return transport

        # No new transport available, handle according to fallback mode
        match self.fallback_mode:
            case FallbackMode.TRY_LEGACY:
                return self._handle_try_legacy(api_mode)

            case FallbackMode.FEATURE_FLAG:
                return self._handle_feature_flag(api_mode)

            case FallbackMode.HARD_FAIL:
                raise TransportNotAvailable(api_mode, "not implemented")

    def _handle_try_legacy(self, api_mode: str) -> any:
        """Handle TRY_LEGACY mode: use legacy dispatcher if available."""
        self._fallback_count[api_mode] = self._fallback_count.get(api_mode, 0) + 1

        logger.warning(
            "No new transport for %r, using legacy path (fallback #%d)",
            api_mode,
            self._fallback_count[api_mode],
        )

        # Emit metric for tracking migration
        self._emit_metric("transport.fallback_legacy", api_mode)

        if self.legacy_dispatcher:
            return self.legacy_dispatcher(api_mode)

        raise TransportNotAvailable(
            api_mode,
            "no legacy dispatcher configured"
        )

    def _handle_feature_flag(self, api_mode: str) -> any:
        """Handle FEATURE_FLAG mode: check env var for provider."""
        env_var = f"USE_LEGACY_{api_mode.upper()}"
        use_legacy = os.getenv(env_var, "").lower() == "true"

        if use_legacy:
            logger.info(
                "%s=true, using legacy transport for %r",
                env_var,
                api_mode,
            )
            self._emit_metric("transport.feature_flag_legacy", api_mode)

            if self.legacy_dispatcher:
                return self.legacy_dispatcher(api_mode)

        raise TransportNotAvailable(
            api_mode,
            f"{env_var} not set to 'true'"
        )

    def _emit_metric(self, metric_name: str, api_mode: str) -> None:
        """Emit telemetry metric for tracking."""
        # This will be connected to actual metrics collection
        # For now, just log
        logger.debug("metric: %s api_mode=%s", metric_name, api_mode)

    def get_fallback_stats(self) -> dict[str, int]:
        """Get count of fallbacks per API mode."""
        return self._fallback_count.copy()

    def clear_fallback_stats(self) -> None:
        """Clear fallback statistics."""
        self._fallback_count.clear()


# Global factory instance
_global_factory: Optional[TransportFactory] = None


def get_global_factory() -> TransportFactory:
    """Get or create global transport factory."""
    global _global_factory
    if _global_factory is None:
        _global_factory = TransportFactory()
    return _global_factory


def set_global_factory(factory: TransportFactory) -> None:
    """Set global transport factory."""
    global _global_factory
    _global_factory = factory
