"""Tests for routing metrics tracking."""

import pytest

from agent.routing_metrics import (
    RoutingMetrics,
    RoutingMetricsTracker,
    get_routing_metrics,
    get_routing_metrics_tracker,
    record_routing_decision,
    record_routing_failure,
    reset_routing_metrics,
)
from agent.routing_types import ModelTier, TaskCategory


class TestRoutingMetrics:
    """Tests for RoutingMetrics dataclass."""

    def test_metrics_initialization(self):
        """RoutingMetrics should initialize with zero values."""
        metrics = RoutingMetrics()
        assert metrics.total_routed == 0
        assert metrics.successful_routings == 0
        assert metrics.failed_routings == 0
        assert metrics.get_success_rate() == 100.0  # No routings yet

    def test_record_successful_routing(self):
        """Recording a successful routing should update metrics."""
        metrics = RoutingMetrics()
        metrics.record_routing_decision(
            tier=ModelTier.BALANCED,
            category=TaskCategory.READ,
            complexity_level="simple",
            confidence=0.8,
            cost_savings=25.0,
        )

        assert metrics.total_routed == 1
        assert metrics.successful_routings == 1
        assert metrics.by_tier[ModelTier.BALANCED.value] == 1
        assert metrics.by_category[TaskCategory.READ.value] == 1
        assert metrics.by_complexity["simple"] == 1
        assert metrics.total_cost_savings_estimate == 25.0
        assert metrics.get_success_rate() == 100.0

    def test_record_multiple_routings(self):
        """Multiple routings should accumulate correctly."""
        metrics = RoutingMetrics()
        for i in range(5):
            metrics.record_routing_decision(
                tier=ModelTier.BALANCED,
                category=TaskCategory.CODE,
                complexity_level="moderate",
                confidence=0.85,
                cost_savings=10.0,
            )

        assert metrics.total_routed == 5
        assert metrics.successful_routings == 5
        assert metrics.by_tier[ModelTier.BALANCED.value] == 5
        assert metrics.by_category[TaskCategory.CODE.value] == 5
        assert metrics.total_cost_savings_estimate == 50.0

    def test_tier_distribution(self):
        """Tier distribution should be tracked correctly."""
        metrics = RoutingMetrics()

        metrics.record_routing_decision(ModelTier.FAST_CHEAP, None, "simple", 0.9, 75.0)
        metrics.record_routing_decision(ModelTier.BALANCED, None, "moderate", 0.8, 25.0)
        metrics.record_routing_decision(ModelTier.CAPABLE, None, "complex", 0.7, 0.0)
        metrics.record_routing_decision(ModelTier.EXTENDED, None, "critical", 0.6, 0.0)

        assert metrics.by_tier[ModelTier.FAST_CHEAP.value] == 1
        assert metrics.by_tier[ModelTier.BALANCED.value] == 1
        assert metrics.by_tier[ModelTier.CAPABLE.value] == 1
        assert metrics.by_tier[ModelTier.EXTENDED.value] == 1

    def test_category_distribution(self):
        """Category distribution should be tracked."""
        metrics = RoutingMetrics()

        for category in TaskCategory:
            metrics.record_routing_decision(
                ModelTier.BALANCED, category, "moderate", 0.8, 0.0
            )

        for category in TaskCategory:
            assert metrics.by_category[category.value] == 1

    def test_complexity_distribution(self):
        """Complexity distribution should be tracked."""
        metrics = RoutingMetrics()

        complexities = ["simple", "moderate", "complex", "critical"]
        for complexity in complexities:
            metrics.record_routing_decision(
                ModelTier.BALANCED, None, complexity, 0.8, 0.0
            )

        for complexity in complexities:
            assert metrics.by_complexity[complexity] == 1

    def test_confidence_tracking(self):
        """Confidence scores should be tracked correctly."""
        metrics = RoutingMetrics()

        confidences = [0.9, 0.8, 0.7, 0.6, 0.5]
        for conf in confidences:
            metrics.record_routing_decision(
                ModelTier.BALANCED, None, "moderate", conf, 0.0
            )

        assert metrics.get_average_confidence() == pytest.approx(0.7, abs=0.01)
        assert metrics.min_confidence == 0.5
        assert metrics.max_confidence == 0.9

    def test_cost_savings_accumulation(self):
        """Cost savings should accumulate."""
        metrics = RoutingMetrics()

        savings = [10.0, 20.0, 30.0, 40.0]
        for saving in savings:
            metrics.record_routing_decision(
                ModelTier.BALANCED, None, "moderate", 0.8, saving
            )

        assert metrics.total_cost_savings_estimate == sum(savings)

    def test_constraint_tracking(self):
        """Constraints applied should be tracked."""
        metrics = RoutingMetrics()

        metrics.record_routing_decision(
            ModelTier.CAPABLE, TaskCategory.SECURITY, "complex", 0.8, 0.0,
            constraint_applied=True, security_upgrade=True
        )

        assert metrics.constraints_applied == 1
        assert metrics.security_upgrades == 1

    def test_failure_recording(self):
        """Failures should be recorded correctly."""
        metrics = RoutingMetrics()

        metrics.record_routing_failure(reason="input_validation", fallback_used=True)

        assert metrics.total_routed == 1
        assert metrics.failed_routings == 1
        assert metrics.input_validation_failures == 1
        assert metrics.fallbacks_used == 1
        assert metrics.get_success_rate() == 0.0

    def test_uncategorized_tasks(self):
        """Tasks without category should be counted as uncategorized."""
        metrics = RoutingMetrics()

        metrics.record_routing_decision(ModelTier.BALANCED, None, "moderate", 0.8, 0.0)

        assert metrics.by_category["uncategorized"] == 1

    def test_reset(self):
        """Reset should clear all metrics."""
        metrics = RoutingMetrics()

        metrics.record_routing_decision(ModelTier.BALANCED, TaskCategory.CODE, "moderate", 0.8, 25.0)
        assert metrics.total_routed == 1

        metrics.reset()

        assert metrics.total_routed == 0
        assert metrics.successful_routings == 0
        assert metrics.total_cost_savings_estimate == 0.0


class TestRoutingMetricsTracker:
    """Tests for thread-safe RoutingMetricsTracker."""

    def test_tracker_initialization(self):
        """Tracker should initialize with empty metrics."""
        tracker = RoutingMetricsTracker()
        metrics = tracker.get_metrics()
        assert metrics.total_routed == 0

    def test_record_via_tracker(self):
        """Recording via tracker should update metrics."""
        tracker = RoutingMetricsTracker()

        tracker.record_routing_decision(
            ModelTier.BALANCED, TaskCategory.CODE, "moderate", 0.8, 25.0
        )

        metrics = tracker.get_metrics()
        assert metrics.total_routed == 1
        assert metrics.successful_routings == 1

    def test_tracker_is_thread_safe(self):
        """Tracker should handle concurrent access."""
        import threading

        tracker = RoutingMetricsTracker()

        def record_routings():
            for i in range(10):
                tracker.record_routing_decision(
                    ModelTier.BALANCED, None, "moderate", 0.8, 10.0
                )

        threads = [threading.Thread(target=record_routings) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        metrics = tracker.get_metrics()
        assert metrics.total_routed == 50
        assert metrics.successful_routings == 50

    def test_tracker_reset(self):
        """Tracker reset should clear metrics."""
        tracker = RoutingMetricsTracker()

        tracker.record_routing_decision(ModelTier.BALANCED, None, "moderate", 0.8, 25.0)
        tracker.reset()

        metrics = tracker.get_metrics()
        assert metrics.total_routed == 0


class TestGlobalMetricsTracker:
    """Tests for global metrics tracking functions."""

    def setup_method(self):
        """Reset global metrics before each test."""
        reset_routing_metrics()

    def test_record_routing_decision_global(self):
        """Global record function should work."""
        record_routing_decision(
            ModelTier.BALANCED, TaskCategory.CODE, "moderate", 0.8, 25.0
        )

        metrics = get_routing_metrics()
        assert metrics.total_routed == 1
        assert metrics.successful_routings == 1

    def test_record_routing_failure_global(self):
        """Global failure function should work."""
        record_routing_failure(reason="input_validation")

        metrics = get_routing_metrics()
        assert metrics.total_routed == 1
        assert metrics.failed_routings == 1

    def test_multiple_global_records(self):
        """Multiple global records should accumulate."""
        for i in range(5):
            record_routing_decision(
                ModelTier.BALANCED, None, "moderate", 0.8, 20.0
            )

        metrics = get_routing_metrics()
        assert metrics.total_routed == 5
        assert metrics.total_cost_savings_estimate == 100.0

    def test_global_reset(self):
        """Global reset should clear all metrics."""
        record_routing_decision(ModelTier.BALANCED, None, "moderate", 0.8, 25.0)
        reset_routing_metrics()

        metrics = get_routing_metrics()
        assert metrics.total_routed == 0


class TestMetricsReporting:
    """Tests for metrics reporting."""

    def setup_method(self):
        """Reset global metrics before each test."""
        reset_routing_metrics()

    def test_metrics_summary(self):
        """Summary should include all key metrics."""
        record_routing_decision(
            ModelTier.BALANCED, TaskCategory.CODE, "moderate", 0.85, 25.0
        )
        record_routing_decision(
            ModelTier.CAPABLE, TaskCategory.SECURITY, "complex", 0.9, 0.0,
            constraint_applied=True, security_upgrade=True
        )

        tracker = get_routing_metrics_tracker()
        summary = tracker.get_summary()

        assert "Total Routed: 2" in summary
        assert "Successful: 2" in summary
        assert "balanced: 1" in summary
        assert "capable: 1" in summary
        assert "code: 1" in summary
        assert "security: 1" in summary
        assert "moderate: 1" in summary
        assert "complex: 1" in summary
        assert "Security Upgrades: 1" in summary

    def test_success_rate_calculation(self):
        """Success rate should be calculated correctly."""
        record_routing_decision(ModelTier.BALANCED, None, "moderate", 0.8, 0.0)
        record_routing_decision(ModelTier.BALANCED, None, "moderate", 0.8, 0.0)
        record_routing_failure()

        metrics = get_routing_metrics()
        assert metrics.get_success_rate() == pytest.approx(66.67, abs=0.01)

    def test_empty_metrics_summary(self):
        """Empty metrics should still produce valid summary."""
        tracker = get_routing_metrics_tracker()
        summary = tracker.get_summary()

        assert "Total Routed: 0" in summary
        assert "Successful: 0" in summary


class TestMetricsEdgeCases:
    """Edge case tests for metrics."""

    def setup_method(self):
        """Reset global metrics before each test."""
        reset_routing_metrics()

    def test_zero_confidence_handling(self):
        """Zero confidence should be handled."""
        record_routing_decision(
            ModelTier.BALANCED, None, "moderate", 0.0, 0.0
        )

        metrics = get_routing_metrics()
        assert metrics.min_confidence == 0.0

    def test_all_failures(self):
        """All failures should be tracked correctly."""
        for _ in range(5):
            record_routing_failure()

        metrics = get_routing_metrics()
        assert metrics.total_routed == 5
        assert metrics.failed_routings == 5
        assert metrics.successful_routings == 0
        assert metrics.get_success_rate() == 0.0

    def test_mixed_failures_and_successes(self):
        """Mixed failures and successes should aggregate correctly."""
        for _ in range(3):
            record_routing_decision(
                ModelTier.BALANCED, None, "moderate", 0.8, 10.0
            )

        for _ in range(2):
            record_routing_failure()

        metrics = get_routing_metrics()
        assert metrics.total_routed == 5
        assert metrics.successful_routings == 3
        assert metrics.failed_routings == 2
        assert metrics.get_success_rate() == 60.0
