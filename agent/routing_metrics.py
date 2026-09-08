"""Cost tracking and metrics for task-aware model routing.

Tracks routing decisions to provide:
- Total cost savings estimates
- Routing decision distribution (which tiers are used)
- Task complexity distribution
- Category distribution
- Performance metrics (success rate, average confidence)
"""

import logging
import threading
from dataclasses import dataclass, field
from typing import Dict, Optional

from agent.routing_types import ModelTier, TaskCategory

logger = logging.getLogger(__name__)


@dataclass
class RoutingMetrics:
    """Metrics for routing decisions."""

    # Decision tracking
    total_routed: int = 0
    by_tier: Dict[str, int] = field(default_factory=lambda: {
        ModelTier.FAST_CHEAP.value: 0,
        ModelTier.BALANCED.value: 0,
        ModelTier.CAPABLE.value: 0,
        ModelTier.EXTENDED.value: 0,
    })
    by_category: Dict[str, int] = field(default_factory=lambda: {
        TaskCategory.READ.value: 0,
        TaskCategory.ANALYZE.value: 0,
        TaskCategory.CODE.value: 0,
        TaskCategory.REASONING.value: 0,
        TaskCategory.RESEARCH.value: 0,
        TaskCategory.SECURITY.value: 0,
        "uncategorized": 0,
    })

    # Complexity distribution
    by_complexity: Dict[str, int] = field(default_factory=lambda: {
        "simple": 0,
        "moderate": 0,
        "complex": 0,
        "critical": 0,
    })

    # Performance metrics
    total_cost_savings_estimate: float = 0.0
    successful_routings: int = 0
    failed_routings: int = 0
    total_confidence: float = 0.0
    min_confidence: float = 1.0
    max_confidence: float = 0.0

    # Constraint tracking
    constraints_applied: int = 0
    security_upgrades: int = 0
    read_downgrades: int = 0

    # Error tracking
    fallbacks_used: int = 0
    input_validation_failures: int = 0
    security_validation_failures: int = 0

    def record_routing_decision(
        self,
        tier: ModelTier,
        category: Optional[TaskCategory],
        complexity_level: str,
        confidence: float,
        cost_savings: Optional[float],
        constraint_applied: bool = False,
        security_upgrade: bool = False,
        fallback_used: bool = False,
    ):
        """Record a routing decision."""
        self.total_routed += 1
        self.by_tier[tier.value] += 1
        self.by_complexity[complexity_level] += 1

        if category:
            self.by_category[category.value] += 1
        else:
            self.by_category["uncategorized"] += 1

        if cost_savings is not None and cost_savings > 0:
            self.total_cost_savings_estimate += cost_savings

        self.total_confidence += confidence
        self.min_confidence = min(self.min_confidence, confidence)
        self.max_confidence = max(self.max_confidence, confidence)

        if constraint_applied:
            self.constraints_applied += 1
        if security_upgrade:
            self.security_upgrades += 1
        if fallback_used:
            self.fallbacks_used += 1

        self.successful_routings += 1

    def record_routing_failure(
        self, reason: str = "unknown", fallback_used: bool = False
    ):
        """Record a routing failure."""
        self.total_routed += 1
        self.failed_routings += 1
        if fallback_used:
            self.fallbacks_used += 1

        if reason == "input_validation":
            self.input_validation_failures += 1
        elif reason == "security_validation":
            self.security_validation_failures += 1

    def get_average_confidence(self) -> float:
        """Get average confidence of successful routings."""
        if self.successful_routings == 0:
            return 0.0
        return self.total_confidence / self.successful_routings

    def get_success_rate(self) -> float:
        """Get success rate as percentage."""
        if self.total_routed == 0:
            return 100.0
        return (self.successful_routings / self.total_routed) * 100.0

    def get_summary(self) -> str:
        """Get a human-readable summary of routing metrics."""
        summary = f"""
Routing Metrics Summary:
  Total Routed: {self.total_routed}
  Successful: {self.successful_routings} ({self.get_success_rate():.1f}%)
  Failed: {self.failed_routings} ({(self.failed_routings/max(1,self.total_routed)*100):.1f}%)

  Tier Distribution:
    fast_cheap: {self.by_tier.get(ModelTier.FAST_CHEAP.value, 0)} ({self._pct(self.by_tier.get(ModelTier.FAST_CHEAP.value, 0))}%)
    balanced: {self.by_tier.get(ModelTier.BALANCED.value, 0)} ({self._pct(self.by_tier.get(ModelTier.BALANCED.value, 0))}%)
    capable: {self.by_tier.get(ModelTier.CAPABLE.value, 0)} ({self._pct(self.by_tier.get(ModelTier.CAPABLE.value, 0))}%)
    extended: {self.by_tier.get(ModelTier.EXTENDED.value, 0)} ({self._pct(self.by_tier.get(ModelTier.EXTENDED.value, 0))}%)

  Category Distribution:
    read: {self.by_category.get(TaskCategory.READ.value, 0)}
    analyze: {self.by_category.get(TaskCategory.ANALYZE.value, 0)}
    code: {self.by_category.get(TaskCategory.CODE.value, 0)}
    reasoning: {self.by_category.get(TaskCategory.REASONING.value, 0)}
    research: {self.by_category.get(TaskCategory.RESEARCH.value, 0)}
    security: {self.by_category.get(TaskCategory.SECURITY.value, 0)}
    uncategorized: {self.by_category.get("uncategorized", 0)}

  Complexity Distribution:
    simple: {self.by_complexity.get("simple", 0)}
    moderate: {self.by_complexity.get("moderate", 0)}
    complex: {self.by_complexity.get("complex", 0)}
    critical: {self.by_complexity.get("critical", 0)}

  Performance:
    Avg Confidence: {self.get_average_confidence():.2f}
    Min/Max Confidence: {self.min_confidence:.2f} / {self.max_confidence:.2f}

  Cost Optimization:
    Total Estimated Savings: {self.total_cost_savings_estimate:.1f}%
    Constraints Applied: {self.constraints_applied}
    Security Upgrades: {self.security_upgrades}
    Read Downgrades: {self.read_downgrades}

  Fallbacks & Errors:
    Fallbacks Used: {self.fallbacks_used}
    Input Validation Failures: {self.input_validation_failures}
    Security Validation Failures: {self.security_validation_failures}
"""
        return summary.strip()

    def _pct(self, value: int) -> str:
        """Format percentage."""
        if self.total_routed == 0:
            return "0"
        return f"{(value/self.total_routed*100):.0f}"

    def reset(self):
        """Reset all metrics."""
        self.total_routed = 0
        self.by_tier = {
            ModelTier.FAST_CHEAP.value: 0,
            ModelTier.BALANCED.value: 0,
            ModelTier.CAPABLE.value: 0,
            ModelTier.EXTENDED.value: 0,
        }
        self.by_category = {
            TaskCategory.READ.value: 0,
            TaskCategory.ANALYZE.value: 0,
            TaskCategory.CODE.value: 0,
            TaskCategory.REASONING.value: 0,
            TaskCategory.RESEARCH.value: 0,
            TaskCategory.SECURITY.value: 0,
            "uncategorized": 0,
        }
        self.by_complexity = {
            "simple": 0,
            "moderate": 0,
            "complex": 0,
            "critical": 0,
        }
        self.total_cost_savings_estimate = 0.0
        self.successful_routings = 0
        self.failed_routings = 0
        self.total_confidence = 0.0
        self.min_confidence = 1.0
        self.max_confidence = 0.0
        self.constraints_applied = 0
        self.security_upgrades = 0
        self.read_downgrades = 0
        self.fallbacks_used = 0
        self.input_validation_failures = 0
        self.security_validation_failures = 0


class RoutingMetricsTracker:
    """Thread-safe tracker for routing metrics."""

    def __init__(self):
        """Initialize metrics tracker."""
        self._metrics = RoutingMetrics()
        self._lock = threading.Lock()

    def record_routing_decision(
        self,
        tier: ModelTier,
        category: Optional[TaskCategory],
        complexity_level: str,
        confidence: float,
        cost_savings: Optional[float],
        constraint_applied: bool = False,
        security_upgrade: bool = False,
        fallback_used: bool = False,
    ):
        """Record a routing decision (thread-safe)."""
        with self._lock:
            self._metrics.record_routing_decision(
                tier=tier,
                category=category,
                complexity_level=complexity_level,
                confidence=confidence,
                cost_savings=cost_savings,
                constraint_applied=constraint_applied,
                security_upgrade=security_upgrade,
                fallback_used=fallback_used,
            )

    def record_routing_failure(
        self, reason: str = "unknown", fallback_used: bool = False
    ):
        """Record a routing failure (thread-safe)."""
        with self._lock:
            self._metrics.record_routing_failure(reason=reason, fallback_used=fallback_used)

    def get_metrics(self) -> RoutingMetrics:
        """Get a copy of current metrics."""
        with self._lock:
            import copy
            return copy.deepcopy(self._metrics)

    def get_summary(self) -> str:
        """Get summary string."""
        metrics = self.get_metrics()
        return metrics.get_summary()

    def reset(self):
        """Reset metrics."""
        with self._lock:
            self._metrics.reset()

    def log_summary(self):
        """Log metrics summary to logger."""
        logger.info("Routing metrics:\n%s", self.get_summary())


# Global metrics tracker instance
_global_metrics_tracker: Optional[RoutingMetricsTracker] = None


def get_routing_metrics_tracker() -> RoutingMetricsTracker:
    """Get or create global metrics tracker."""
    global _global_metrics_tracker
    if _global_metrics_tracker is None:
        _global_metrics_tracker = RoutingMetricsTracker()
    return _global_metrics_tracker


def record_routing_decision(
    tier: ModelTier,
    category: Optional[TaskCategory],
    complexity_level: str,
    confidence: float,
    cost_savings: Optional[float],
    constraint_applied: bool = False,
    security_upgrade: bool = False,
    fallback_used: bool = False,
):
    """Record a routing decision to global metrics."""
    get_routing_metrics_tracker().record_routing_decision(
        tier=tier,
        category=category,
        complexity_level=complexity_level,
        confidence=confidence,
        cost_savings=cost_savings,
        constraint_applied=constraint_applied,
        security_upgrade=security_upgrade,
        fallback_used=fallback_used,
    )


def record_routing_failure(reason: str = "unknown", fallback_used: bool = False):
    """Record a routing failure to global metrics."""
    get_routing_metrics_tracker().record_routing_failure(reason=reason, fallback_used=fallback_used)


def get_routing_metrics() -> RoutingMetrics:
    """Get current routing metrics."""
    return get_routing_metrics_tracker().get_metrics()


def log_routing_metrics():
    """Log routing metrics summary."""
    get_routing_metrics_tracker().log_summary()


def reset_routing_metrics():
    """Reset all routing metrics."""
    get_routing_metrics_tracker().reset()
