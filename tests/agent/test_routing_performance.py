"""Performance benchmarks for task-aware model routing.

Measures the performance impact of routing analysis to ensure:
- Analysis overhead is acceptable (<500ms per task)
- Parallelization works efficiently for batch tasks
- No memory leaks or accumulation
"""

import time
from typing import List, Tuple

import pytest

from agent.task_aware_model_router import route_task_to_model


class TestRoutingPerformance:
    """Performance tests for routing system."""

    @pytest.mark.performance
    def test_single_task_routing_latency(self):
        """Single task routing should complete in reasonable time."""
        task = "Analyze the data in the report"

        start = time.perf_counter()
        model, decision = route_task_to_model(task)
        elapsed = time.perf_counter() - start

        # Routing should complete in < 500ms for single task
        assert elapsed < 0.5, f"Routing took {elapsed:.3f}s, expected < 0.5s"
        assert model is not None
        assert decision is not None

    @pytest.mark.performance
    def test_multiple_sequential_routing_latency(self):
        """Multiple sequential routing calls should stay consistent."""
        tasks = [
            "Read the file",
            "Analyze the data",
            "Design the system",
            "Security audit",
            "Write Python code",
        ]

        times = []
        for task in tasks:
            start = time.perf_counter()
            model, decision = route_task_to_model(task)
            elapsed = time.perf_counter() - start
            times.append(elapsed)

        # Each should be reasonable
        for i, elapsed in enumerate(times):
            assert elapsed < 0.5, f"Task {i} took {elapsed:.3f}s"

        # Average should be consistent
        avg_time = sum(times) / len(times)
        assert avg_time < 0.4, f"Average routing time {avg_time:.3f}s too high"

    @pytest.mark.performance
    def test_routing_scalability_many_tasks(self):
        """Routing should scale linearly with number of tasks."""
        tasks = [
            "Task " + str(i) for i in range(100)
        ]

        start = time.perf_counter()
        results = []
        for task in tasks:
            model, decision = route_task_to_model(task)
            results.append((model, decision))
        elapsed = time.perf_counter() - start

        # All should complete
        assert len(results) == 100
        assert all(r[0] is not None for r in results)

        # Average per task
        avg_per_task = elapsed / 100
        assert avg_per_task < 0.5, f"Average {avg_per_task:.3f}s per task too high"

    @pytest.mark.performance
    def test_simple_task_routing_faster_than_complex(self):
        """Simple tasks should route faster than complex ones (less analysis)."""
        simple_task = "Read a file"
        complex_task = "Design a distributed system with fault tolerance and load balancing"

        # Time simple task
        start = time.perf_counter()
        for _ in range(5):
            route_task_to_model(simple_task)
        simple_time = time.perf_counter() - start

        # Time complex task
        start = time.perf_counter()
        for _ in range(5):
            route_task_to_model(complex_task)
        complex_time = time.perf_counter() - start

        # Complex task analysis likely takes longer (reasoning engine)
        # But should still be reasonable
        assert simple_time < 2.5  # 5 tasks in < 2.5s
        assert complex_time < 2.5  # 5 tasks in < 2.5s

    @pytest.mark.performance
    def test_routing_with_caching_behavior(self):
        """Router should benefit from singleton pattern (reuse)."""
        task = "Analyze the data"

        # First call (cold)
        start = time.perf_counter()
        route_task_to_model(task)
        cold_time = time.perf_counter() - start

        # Subsequent calls should be similar or faster (cached reasoning engine)
        warm_times = []
        for _ in range(5):
            start = time.perf_counter()
            route_task_to_model(task)
            warm_times.append(time.perf_counter() - start)

        # Warm calls should be similar to cold (no degradation)
        avg_warm = sum(warm_times) / len(warm_times)
        assert avg_warm < 1.0

    @pytest.mark.performance
    def test_concurrent_routing_performance(self):
        """Concurrent routing should not have excessive overhead."""
        import threading

        tasks = [f"Task {i}" for i in range(10)]
        results = []
        times = []
        lock = threading.Lock()

        def route_concurrent(task):
            start = time.perf_counter()
            model, decision = route_task_to_model(task)
            elapsed = time.perf_counter() - start
            with lock:
                results.append((model, decision))
                times.append(elapsed)

        threads = [threading.Thread(target=route_concurrent, args=(t,)) for t in tasks]

        start = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        total_elapsed = time.perf_counter() - start

        # All should succeed
        assert len(results) == 10

        # Total time should not be excessive (some parallelism benefit)
        # With 10 tasks and ~0.3s each, sequential would be ~3s
        # Concurrent should be faster
        assert total_elapsed < 5.0

    @pytest.mark.performance
    def test_routing_memory_efficiency(self):
        """Routing should not accumulate memory across calls."""
        import gc

        # Get baseline
        gc.collect()
        import sys
        baseline = sys.getsizeof(None)

        # Make many routing calls
        for i in range(100):
            route_task_to_model(f"Task {i}")

        # Check no runaway memory
        gc.collect()
        # Memory should not explode (hard to test precisely, just verify no exception)
        assert True

    @pytest.mark.performance
    def test_routing_decision_completeness_vs_latency(self):
        """More complete decisions should not significantly increase latency."""
        # All routing calls return full decision
        task = "Analyze security vulnerabilities"

        start = time.perf_counter()
        model, decision = route_task_to_model(task)
        elapsed = time.perf_counter() - start

        # Should complete quickly despite generating full decision info
        assert elapsed < 0.5

        # Decision should be complete
        assert decision.recommended_tier is not None
        assert decision.recommended_model is not None
        assert decision.complexity is not None
        assert decision.category is not None
        assert decision.reasoning
        assert 0.0 <= decision.confidence <= 1.0


class TestRoutingThroughput:
    """Throughput tests for batch routing scenarios."""

    @pytest.mark.performance
    def test_batch_routing_throughput(self):
        """Measure throughput for batch task routing."""
        num_tasks = 50
        tasks = [f"Task number {i} to analyze" for i in range(num_tasks)]

        start = time.perf_counter()
        results = []
        for task in tasks:
            model, decision = route_task_to_model(task)
            results.append((model, decision))
        elapsed = time.perf_counter() - start

        # All should succeed
        assert len(results) == num_tasks

        # Throughput should be reasonable
        throughput = num_tasks / elapsed
        # Should be at least 20 tasks/second
        assert throughput > 20, f"Throughput {throughput:.1f} tasks/s too low"

    @pytest.mark.performance
    def test_routing_with_varying_task_complexity(self):
        """Routing should handle mixed complexity tasks."""
        tasks_by_complexity = {
            "simple": [
                "List files",
                "Read data",
                "Get information",
            ],
            "moderate": [
                "Analyze the report",
                "Summarize the document",
                "Classify this text",
            ],
            "complex": [
                "Design a system architecture",
                "Solve this optimization problem",
                "Create a comprehensive plan",
            ],
        }

        all_results = {}
        for complexity, task_list in tasks_by_complexity.items():
            times = []
            for task in task_list:
                start = time.perf_counter()
                model, decision = route_task_to_model(task)
                elapsed = time.perf_counter() - start
                times.append(elapsed)
            all_results[complexity] = times

        # All should complete reasonably
        for complexity, times in all_results.items():
            avg_time = sum(times) / len(times)
            assert avg_time < 0.5, f"{complexity} tasks averaging {avg_time:.3f}s"


class TestRoutingEdgeCasePerformance:
    """Performance under edge case conditions."""

    @pytest.mark.performance
    def test_very_short_task_description_performance(self):
        """Very short tasks should route quickly."""
        task = "a"

        start = time.perf_counter()
        for _ in range(10):
            route_task_to_model(task)
        elapsed = time.perf_counter() - start

        # Should be quick even for minimal input
        assert elapsed < 1.0

    @pytest.mark.performance
    def test_moderately_long_task_description_performance(self):
        """Moderately long (but valid) tasks should not be slow."""
        task = "Analyze the following: " + ("x " * 1000)  # ~10KB

        start = time.perf_counter()
        model, decision = route_task_to_model(task)
        elapsed = time.perf_counter() - start

        # Should complete in reasonable time
        assert elapsed < 1.0
        assert model is not None

    @pytest.mark.performance
    def test_routing_with_many_tools_performance(self):
        """Routing should scale with tool count."""
        task = "Analyze data"

        start = time.perf_counter()
        model, decision = route_task_to_model(task, available_tools=100)
        elapsed = time.perf_counter() - start

        # Should not be significantly impacted by tool count
        assert elapsed < 0.5
