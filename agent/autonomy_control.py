"""Autonomy levels and safety controls.

Implements:
- Autonomy level selection (human → semi-auto → full)
- Approval gates
- Resource limits
- Rollback capabilities
"""

from enum import Enum
from dataclasses import dataclass
from typing import Callable, Optional, Any, Dict


class AutonomyLevel(Enum):
    """Autonomy levels for agent behavior."""
    HUMAN_ONLY = 0  # Requires approval for everything
    HUMAN_PLUS = 1  # Runs analysis, needs approval for execution
    SEMI_AUTO = 2  # Executes safe operations automatically
    FULL_AUTO = 3  # Full autonomy with resource limits


@dataclass
class ResourceLimits:
    """Resource constraints for autonomous execution."""
    max_api_calls: int = 50
    max_tokens_per_call: int = 4000
    max_file_writes: int = 20
    max_execution_time_s: int = 300
    max_cost_usd: float = 10.0


class AutonomyController:
    """Manages autonomy levels and approvals."""

    def __init__(
        self,
        level: AutonomyLevel = AutonomyLevel.HUMAN_PLUS,
        limits: Optional[ResourceLimits] = None,
    ):
        self.level = level
        self.limits = limits or ResourceLimits()
        self.approval_fn: Optional[Callable[[str], bool]] = None
        self.usage = {
            "api_calls": 0,
            "tokens_used": 0,
            "files_written": 0,
            "execution_time_s": 0,
            "cost_usd": 0.0,
        }

    def set_approval_fn(self, fn: Callable[[str], bool]):
        """Set approval callback function."""
        self.approval_fn = fn

    def request_approval(self, operation: str) -> bool:
        """Request approval for operation."""
        if self.level == AutonomyLevel.HUMAN_ONLY:
            return self.approval_fn(operation) if self.approval_fn else False

        if self.level in [AutonomyLevel.HUMAN_PLUS, AutonomyLevel.SEMI_AUTO]:
            # Check if operation is risky
            if self._is_risky(operation):
                return self.approval_fn(operation) if self.approval_fn else False
            return True

        # Full autonomy
        return self._check_resource_limits(operation)

    def _is_risky(self, operation: str) -> bool:
        """Check if operation is risky."""
        risky_keywords = ["delete", "drop", "remove", "shutdown", "uninstall"]
        return any(kw in operation.lower() for kw in risky_keywords)

    def _check_resource_limits(self, operation: str) -> bool:
        """Check if operation respects resource limits."""
        if self.usage["api_calls"] >= self.limits.max_api_calls:
            return False
        if self.usage["tokens_used"] >= self.limits.max_tokens_per_call:
            return False
        if self.usage["cost_usd"] >= self.limits.max_cost_usd:
            return False
        return True

    def record_usage(
        self,
        api_calls: int = 0,
        tokens_used: int = 0,
        files_written: int = 0,
        execution_time_s: float = 0,
        cost_usd: float = 0.0,
    ):
        """Record resource usage."""
        self.usage["api_calls"] += api_calls
        self.usage["tokens_used"] += tokens_used
        self.usage["files_written"] += files_written
        self.usage["execution_time_s"] += execution_time_s
        self.usage["cost_usd"] += cost_usd

    def can_execute(self, operation: str) -> bool:
        """Check if operation can be executed."""
        if not self._check_resource_limits(operation):
            return False
        return self.request_approval(operation)

    def get_status(self) -> Dict[str, Any]:
        """Get current autonomy status."""
        return {
            "level": self.level.name,
            "limits": {
                "max_api_calls": self.limits.max_api_calls,
                "max_tokens_per_call": self.limits.max_tokens_per_call,
                "max_file_writes": self.limits.max_file_writes,
                "max_execution_time_s": self.limits.max_execution_time_s,
                "max_cost_usd": self.limits.max_cost_usd,
            },
            "usage": self.usage,
            "remaining": {
                "api_calls": self.limits.max_api_calls - self.usage["api_calls"],
                "tokens_per_call": self.limits.max_tokens_per_call - self.usage["tokens_used"],
                "file_writes": self.limits.max_file_writes - self.usage["files_written"],
                "execution_time_s": self.limits.max_execution_time_s - self.usage["execution_time_s"],
                "cost_usd": self.limits.max_cost_usd - self.usage["cost_usd"],
            },
        }


__all__ = ["AutonomyController", "AutonomyLevel", "ResourceLimits"]
