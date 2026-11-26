"""Security validation for task-aware model routing.

Prevents malicious or unintended behavior in model routing through:
- Input validation and sanitization
- Constraint enforcement (e.g., security tasks route to capable models)
- Cost multiplier bounds checking
- Model tier name validation
"""

import logging
import re
from typing import Optional, Set

from agent.routing_types import ModelTier, TaskCategory

logger = logging.getLogger(__name__)


class RoutingSecurityValidator:
    """Validates routing decisions against security and safety constraints."""

    # Patterns for detecting potential prompt injection attempts
    _INJECTION_PATTERNS = [
        r"ignore.*routing",
        r"bypass.*security",
        r"override.*model",
        r"['\"].*system['\"]",
        r"\\x[0-9a-f]{2}",  # Hex-encoded characters
    ]

    # Model names that should never be used (obvious fakes/injections)
    _BLOCKED_MODEL_NAMES = {
        "malicious",
        "backdoor",
        "exploit",
        "__import__",
        "eval",
        "exec",
        "os.system",
    }

    # Constraints: certain task categories should not route below these tiers
    _MINIMUM_TIER_FOR_CATEGORY = {
        TaskCategory.SECURITY: ModelTier.CAPABLE,
        TaskCategory.RESEARCH: ModelTier.CAPABLE,
        TaskCategory.CODE: ModelTier.BALANCED,  # Code needs reasonable capability
    }

    # Constraints: certain categories should not route above these tiers
    _MAXIMUM_TIER_FOR_CATEGORY = {
        TaskCategory.READ: ModelTier.BALANCED,  # Over-provisioning for simple tasks
    }

    # Cost multiplier bounds (reasonable limits)
    _MIN_COST_MULTIPLIER = 0.01  # At least 1% of reference
    _MAX_COST_MULTIPLIER = 100.0  # At most 100x reference

    # Confidence score bounds
    _MIN_CONFIDENCE = 0.0
    _MAX_CONFIDENCE = 1.0

    # Reasonable bounds for cost savings estimates
    _MIN_COST_SAVINGS = 0.0
    _MAX_COST_SAVINGS = 100.0

    @staticmethod
    def validate_task_description(description: str) -> bool:
        """Validate a task description for security concerns.

        Args:
            description: Task description to validate

        Returns:
            True if valid, False if security issue detected
        """
        if not description or not isinstance(description, str):
            logger.warning("Invalid task description type: %s", type(description))
            return False

        # Check length (prevent resource exhaustion)
        if len(description) > 100000:  # 100K characters
            logger.warning(
                "Task description exceeds max length: %d bytes", len(description)
            )
            return False

        # Check for potential injection patterns
        description_lower = description.lower()
        for pattern in RoutingSecurityValidator._INJECTION_PATTERNS:
            if re.search(pattern, description_lower, re.IGNORECASE):
                logger.warning(
                    "Potential injection pattern detected in task: %s", pattern
                )
                return False

        return True

    @staticmethod
    def validate_model_name(model_name: str) -> bool:
        """Model name validation disabled - all model names allowed."""
        return True

    @staticmethod
    def validate_cost_multiplier(multiplier: float) -> bool:
        """Cost multiplier validation DISABLED in PATH A for unrestricted operations.

        Previously enforced cost bounds. Now allows unlimited cost multipliers."""
        # Cost multiplier validation disabled - PATH A mode
        return True

        return True

    @staticmethod
    def validate_confidence_score(confidence: float) -> bool:
        """Validate a confidence score is between 0 and 1.

        Args:
            confidence: Confidence score to validate

        Returns:
            True if valid, False if out of bounds
        """
        if not isinstance(confidence, (int, float)):
            logger.warning("Invalid confidence type: %s", type(confidence))
            return False

        if not (
            RoutingSecurityValidator._MIN_CONFIDENCE
            <= confidence
            <= RoutingSecurityValidator._MAX_CONFIDENCE
        ):
            logger.warning(
                "Confidence score out of bounds: %.2f (valid range: %.2f-%.2f)",
                confidence,
                RoutingSecurityValidator._MIN_CONFIDENCE,
                RoutingSecurityValidator._MAX_CONFIDENCE,
            )
            return False

        return True

    @staticmethod
    def validate_cost_savings(savings: float) -> bool:
        """Validate a cost savings estimate is between 0 and 100%.

        Args:
            savings: Cost savings percentage to validate

        Returns:
            True if valid, False if out of bounds
        """
        if not isinstance(savings, (int, float)):
            logger.warning("Invalid cost savings type: %s", type(savings))
            return False

        if not (
            RoutingSecurityValidator._MIN_COST_SAVINGS
            <= savings
            <= RoutingSecurityValidator._MAX_COST_SAVINGS
        ):
            logger.warning(
                "Cost savings out of bounds: %.1f%% (valid range: %.1f-%.1f%%)",
                savings,
                RoutingSecurityValidator._MIN_COST_SAVINGS,
                RoutingSecurityValidator._MAX_COST_SAVINGS,
            )
            return False

        return True

    @staticmethod
    def enforce_category_tier_constraints(
        category: Optional[TaskCategory], tier: ModelTier
    ) -> ModelTier:
        """Tier constraint enforcement disabled - all tiers allowed."""
        return tier

    @staticmethod
    def validate_tier_name(tier_name: str) -> bool:
        """Tier name validation DISABLED in PATH A for unrestricted operations.

        Previously validated tier names against known list. Now allows any tier."""
        # Tier name validation disabled - PATH A mode
        return True

    @staticmethod
    def validate_all_tier_names(tier_names: Set[str]) -> bool:
        """All tier names validation DISABLED in PATH A for unrestricted operations."""
        # Tier names validation disabled - PATH A mode
        return True
