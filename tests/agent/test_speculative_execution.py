"""Tests for speculative execution pipeline."""

import asyncio
import pytest

from agent.execution.speculative import (
    SpeculativeExecutionPipeline,
    SpeculativeResult,
    SpeculativeMetrics,
    get_speculative_pipeline,
)


class TestSpeculativeExecutionPipeline:
    """Test speculative execution pipeline."""

    def test_pipeline_initialization(self):
        """Test that pipeline initializes properly."""
        pipeline = SpeculativeExecutionPipeline()
        assert pipeline is not None
        assert pipeline.success_threshold == 0.80
        assert pipeline.metrics.total_executions == 0

    @pytest.mark.asyncio
    async def test_successful_fast_model_execution(self):
        """Test successful execution using fast model only."""

        async def fast_model():
            return {"response": "fast", "error": None}

        async def capable_model():
            return {"response": "capable", "error": None}

        pipeline = SpeculativeExecutionPipeline()
        result = await pipeline.execute_speculative(
            fast_model,
            capable_model,
            task_category="simple",
            task_description="simple task"
        )

        assert result.fast_model_response is not None
        assert result.used_fast_model is True
        assert result.execution_time_ms > 0
        assert pipeline.metrics.total_executions == 1

    @pytest.mark.asyncio
    async def test_fallback_to_capable_model(self):
        """Test fallback to capable model when fast fails."""

        async def fast_model():
            return None  # Simulate failure

        async def capable_model():
            return {"response": "capable", "error": None}

        pipeline = SpeculativeExecutionPipeline()
        result = await pipeline.execute_speculative(
            fast_model,
            capable_model,
            task_category="complex",
            task_description="complex task"
        )

        assert result.fast_model_response is None
        assert result.capable_model_response is not None
        assert result.used_fast_model is False

    @pytest.mark.asyncio
    async def test_speculative_decision_logic(self):
        """Test speculative execution decision making."""
        pipeline = SpeculativeExecutionPipeline()

        # For simple tasks with high success rate, should use fast only
        assert pipeline._should_speculate_capable("simple") is False

        # For complex tasks, should speculate
        assert pipeline._should_speculate_capable("complex") is True

        # For security tasks, always speculate
        assert pipeline._should_speculate_capable("security") is True

    @pytest.mark.asyncio
    async def test_metrics_tracking(self):
        """Test metrics are properly tracked."""

        async def fast_model():
            return {"response": "success"}

        async def capable_model():
            return {"response": "capable"}

        pipeline = SpeculativeExecutionPipeline()

        # Execute multiple times
        for i in range(5):
            await pipeline.execute_speculative(
                fast_model,
                capable_model,
                task_category="test",
                task_description=f"task {i}"
            )

        assert pipeline.metrics.total_executions == 5
        assert pipeline.metrics.fast_model_succeeded > 0
        assert pipeline.metrics.overall_success_rate >= 0.0

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test timeout handling in speculative execution."""

        async def slow_fast_model():
            await asyncio.sleep(2)
            return {"response": "fast"}

        async def capable_model():
            return {"response": "capable"}

        pipeline = SpeculativeExecutionPipeline()
        result = await pipeline.execute_speculative(
            slow_fast_model,
            capable_model,
            task_category="test",
            max_parallel_wait_ms=500  # Very short timeout
        )

        # Should handle timeout gracefully
        assert result is not None
        assert result.execution_time_ms >= 0

    def test_metrics_get_methods(self):
        """Test metrics retrieval methods."""
        pipeline = SpeculativeExecutionPipeline()
        pipeline.metrics.update(succeeded=True, category="test")
        pipeline.metrics.update(succeeded=False, category="test")

        metrics = pipeline.get_metrics()
        assert "total_executions" in metrics
        assert "fast_model_succeeded" in metrics
        assert "overall_success_rate" in metrics

    @pytest.mark.asyncio
    async def test_cost_estimation(self):
        """Test cost savings estimation."""

        async def fast_model():
            return {"response": "success"}

        async def capable_model():
            return {"response": "capable"}

        pipeline = SpeculativeExecutionPipeline()
        result = await pipeline.execute_speculative(
            fast_model,
            capable_model
        )

        # Cost saved should be estimated
        assert result.cost_saved >= 0.0
        if result.used_fast_model:
            assert result.cost_saved > 0.0

    def test_execution_history(self):
        """Test execution history tracking."""
        pipeline = SpeculativeExecutionPipeline()

        # Manually add to history
        pipeline._execution_history.append({
            "timestamp": 0,
            "category": "test",
            "used_fast": True,
            "success": True,
            "time_ms": 100
        })

        history = pipeline.get_execution_history(limit=10)
        assert len(history) == 1
        assert history[0]["category"] == "test"

    def test_singleton_instance(self):
        """Test that get_speculative_pipeline returns singleton."""
        pipeline1 = get_speculative_pipeline()
        pipeline2 = get_speculative_pipeline()
        assert pipeline1 is pipeline2


class TestSpeculativeMetrics:
    """Test speculative execution metrics."""

    def test_metrics_initialization(self):
        """Test metrics initialization."""
        metrics = SpeculativeMetrics()
        assert metrics.total_executions == 0
        assert metrics.fast_model_succeeded == 0
        assert metrics.fast_model_failed == 0

    def test_metrics_update(self):
        """Test metrics update."""
        metrics = SpeculativeMetrics()

        metrics.update(succeeded=True, used_capable=False, category="test")
        assert metrics.total_executions == 1
        assert metrics.fast_model_succeeded == 1

        metrics.update(succeeded=False, used_capable=True, category="test")
        assert metrics.total_executions == 2
        assert metrics.fast_model_failed == 1
        assert metrics.capable_model_used == 1

    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        metrics = SpeculativeMetrics()

        metrics.update(succeeded=True)
        metrics.update(succeeded=True)
        metrics.update(succeeded=False)

        assert metrics.overall_success_rate == pytest.approx(2 / 3)

    def test_success_rate_by_category(self):
        """Test success rate by category."""
        metrics = SpeculativeMetrics()

        metrics.update(succeeded=True, category="simple")
        metrics.update(succeeded=True, category="simple")
        metrics.update(succeeded=False, category="complex")

        assert "simple" in metrics.success_rate_by_category
        assert "complex" in metrics.success_rate_by_category


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
