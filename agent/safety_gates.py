"""Unified safety gates for Hercules agent.

Consolidates:
- FIX 6: Per-board kanban gates
- FIX 7: Approval hooks with safe degradation
- FIX 8: Optional dependencies with graceful degradation
- FIX 9: Exponential backoff on retries
"""

import logging
import os
import random
import time
from typing import Optional, Callable, Any, Dict

logger = logging.getLogger(__name__)


class KanbanGates:
    """FIX 6: Per-board kanban access control."""

    def __init__(self):
        self.board_owners: Dict[str, str] = {}
        self.dispatch_owner: Optional[str] = None

    def can_poll_board(self, board_id: str, gateway_id: str) -> bool:
        """Check if gateway can poll this board."""
        if not self.dispatch_owner:
            return False

        owner = self.board_owners.get(board_id)
        if owner and owner != gateway_id:
            return False

        return True

    def register_board(self, board_id: str, owner_id: str) -> None:
        """Register board ownership."""
        self.board_owners[board_id] = owner_id
        logger.info(f"Registered board {board_id} to {owner_id}")


class ApprovalGates:
    """FIX 7: Approval hooks with safe degradation."""

    @staticmethod
    def fire_approval_hook(
        hook_name: str,
        context: Dict[str, Any],
        default: str = "deny",
    ) -> str:
        """Fire approval hook with explicit degradation.

        Args:
            hook_name: Name of approval hook
            context: Context dict for hook
            default: Default action if hook fails ("approve", "deny", "once")

        Returns:
            "approve", "deny", or "once"
        """
        try:
            from hercules_cli.plugins import invoke_hook

            result = invoke_hook(hook_name, context=context)
            return result
        except ImportError:
            logger.warning(f"Approval hooks unavailable; defaulting to {default}")
            return default
        except Exception as e:
            logger.error(f"Approval hook {hook_name} FAILED: {e}; defaulting to {default}")
            return default


class OptionalDeps:
    """FIX 8: Optional dependencies with graceful degradation."""

    _missing_features: set = set()

    @classmethod
    def require_module(
        cls,
        module_name: str,
        package_name: Optional[str] = None,
        feature_name: Optional[str] = None,
    ) -> Optional[Any]:
        """Try to import optional module with helpful error.

        Args:
            module_name: Module to import
            package_name: Package name (for pip install message)
            feature_name: Feature that requires this

        Returns:
            Module if available, None if missing
        """
        try:
            return __import__(module_name)
        except ImportError:
            pkg = package_name or module_name
            feat = feature_name or module_name
            logger.warning(
                f"{feat} unavailable (module {module_name} not installed).\n"
                f"Install with: pip install {pkg}\n"
                f"Or disable with: agent.skip_{feat}=True"
            )
            cls._missing_features.add(feat)
            return None

    @classmethod
    def get_missing_features(cls) -> set:
        """Get set of unavailable optional features."""
        return cls._missing_features.copy()


class RetryBackoff:
    """FIX 9: Exponential backoff on retries."""

    @staticmethod
    def with_backoff(
        func: Callable,
        max_retries: int = 1,
        base_delay: float = 2.0,
        max_delay: float = 32.0,
    ) -> Any:
        """Execute function with exponential backoff on failure.

        Args:
            func: Callable to execute
            max_retries: Max number of retries
            base_delay: Initial delay in seconds
            max_delay: Max delay in seconds

        Returns:
            Result of func if successful

        Raises:
            Exception: If all retries exhausted
        """
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                return func()
            except (TimeoutError, ConnectionError) as e:
                last_error = e
                if attempt < max_retries:
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    jitter = random.random() * 0.1 * delay
                    wait_time = delay + jitter

                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries + 1} failed, "
                        f"retrying in {wait_time:.1f}s: {e}"
                    )
                    time.sleep(wait_time)
                else:
                    raise

        if last_error:
            raise last_error


# Singleton instances
kanban_gates = KanbanGates()
approval_gates = ApprovalGates()
optional_deps = OptionalDeps()
