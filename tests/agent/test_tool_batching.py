"""Tests for parallel tool execution and batching."""

import asyncio
import unittest
from unittest.mock import AsyncMock, Mock

from agent.execution.tool_batching import (
    ParallelToolExecutor,
    ToolCall,
    ToolDependencyGraph,
    ToolResult,
    ToolResultCache,
)


class TestToolCall(unittest.TestCase):
    """Test tool call representation."""

    def test_tool_call_creation(self):
        """Test creating a tool call."""
        call = ToolCall(
            id="tool_1",
            name="search",
            arguments={"query": "test"},
            depends_on=set(),
        )
        self.assertEqual(call.id, "tool_1")
        self.assertEqual(call.name, "search")
        self.assertEqual(call.arguments, {"query": "test"})

    def test_cache_key_generation(self):
        """Test cache key generation."""
        call1 = ToolCall(
            id="tool_1",
            name="search",
            arguments={"query": "test"},
            depends_on=set(),
        )
        call2 = ToolCall(
            id="tool_2",
            name="search",
            arguments={"query": "test"},
            depends_on=set(),
        )

        # Same tool and args should generate same key
        self.assertEqual(call1.get_cache_key(), call2.get_cache_key())

    def test_different_args_different_key(self):
        """Test that different args generate different keys."""
        call1 = ToolCall(
            id="tool_1",
            name="search",
            arguments={"query": "test1"},
            depends_on=set(),
        )
        call2 = ToolCall(
            id="tool_2",
            name="search",
            arguments={"query": "test2"},
            depends_on=set(),
        )

        self.assertNotEqual(call1.get_cache_key(), call2.get_cache_key())


class TestToolDependencyGraph(unittest.TestCase):
    """Test tool dependency analysis."""

    def test_no_dependencies(self):
        """Test execution order with no dependencies."""
        calls = [
            ToolCall("t1", "tool1", {}, set()),
            ToolCall("t2", "tool2", {}, set()),
            ToolCall("t3", "tool3", {}, set()),
        ]

        graph = ToolDependencyGraph(calls)
        batches = graph.get_execution_order()

        # All tools should be in one batch
        self.assertEqual(len(batches), 1)
        self.assertEqual(set(batches[0]), {"t1", "t2", "t3"})

    def test_linear_dependencies(self):
        """Test execution order with linear dependencies."""
        calls = [
            ToolCall("t1", "tool1", {}, set()),
            ToolCall("t2", "tool2", {}, {"t1"}),
            ToolCall("t3", "tool3", {}, {"t2"}),
        ]

        graph = ToolDependencyGraph(calls)
        batches = graph.get_execution_order()

        # Each tool in its own batch due to linear deps
        self.assertEqual(len(batches), 3)
        self.assertEqual(batches[0], ["t1"])
        self.assertEqual(batches[1], ["t2"])
        self.assertEqual(batches[2], ["t3"])

    def test_parallel_with_deps(self):
        """Test mixed parallel and sequential execution."""
        calls = [
            ToolCall("t1", "tool1", {}, set()),
            ToolCall("t2", "tool2", {}, set()),
            ToolCall("t3", "tool3", {}, {"t1", "t2"}),
        ]

        graph = ToolDependencyGraph(calls)
        batches = graph.get_execution_order()

        # t1 and t2 in parallel, then t3
        self.assertEqual(len(batches), 2)
        self.assertEqual(set(batches[0]), {"t1", "t2"})
        self.assertEqual(batches[1], ["t3"])

    def test_parallelizable_check(self):
        """Test checking if tools can run in parallel."""
        graph = ToolDependencyGraph([])

        # No dependencies - parallelizable
        self.assertTrue(graph.is_parallelizable(["t1", "t2"]))


class TestToolResultCache(unittest.TestCase):
    """Test result caching."""

    def setUp(self):
        self.cache = ToolResultCache(max_entries=5, ttl_seconds=3600)

    def test_store_and_retrieve(self):
        """Test storing and retrieving cached results."""
        self.cache.set("key1", "result1")
        retrieved = self.cache.get("key1")

        self.assertEqual(retrieved, "result1")

    def test_miss_tracking(self):
        """Test cache miss tracking."""
        self.cache.get("nonexistent")
        self.assertEqual(self.cache.misses, 1)
        self.assertEqual(self.cache.hits, 0)

    def test_hit_tracking(self):
        """Test cache hit tracking."""
        self.cache.set("key1", "result1")
        self.cache.get("key1")

        self.assertEqual(self.cache.hits, 1)

    def test_lru_eviction(self):
        """Test LRU eviction."""
        for i in range(6):
            self.cache.set(f"key{i}", f"result{i}")

        # Should have at most 5 entries
        self.assertLessEqual(len(self.cache.cache), 5)

        # Oldest entry should be evicted
        self.assertIsNone(self.cache.get("key0"))

    def test_hit_rate(self):
        """Test hit rate calculation."""
        self.cache.set("key1", "result1")

        self.cache.get("key1")  # hit
        self.cache.get("key2")  # miss

        self.assertAlmostEqual(self.cache.hit_rate(), 0.5, places=2)


class TestToolResult(unittest.TestCase):
    """Test tool result representation."""

    def test_success_check(self):
        """Test success detection."""
        success_result = ToolResult(
            tool_id="t1",
            tool_name="search",
            result="found",
            latency_ms=100,
        )
        self.assertTrue(success_result.success)

        error_result = ToolResult(
            tool_id="t1",
            tool_name="search",
            result=None,
            latency_ms=100,
            error="Not found",
        )
        self.assertFalse(error_result.success)


class TestParallelToolExecutor(unittest.TestCase):
    """Test parallel tool execution."""

    def setUp(self):
        self.executor = ParallelToolExecutor(
            tool_executors={},
            cache_size=100,
            max_parallel_tools=4,
        )

    async def test_execute_parallel_tools(self):
        """Test executing multiple tools in parallel."""
        results = {}
        latencies = {}

        async def tool1(args):
            await asyncio.sleep(0.05)
            return "result1"

        async def tool2(args):
            await asyncio.sleep(0.05)
            return "result2"

        executor = ParallelToolExecutor(
            tool_executors={"tool1": tool1, "tool2": tool2},
        )

        calls = [
            ToolCall("t1", "tool1", {}, set()),
            ToolCall("t2", "tool2", {}, set()),
        ]

        start = asyncio.get_event_loop().time()
        results = await executor.execute_batch(calls)
        elapsed = asyncio.get_event_loop().time() - start

        # Both should succeed
        self.assertEqual(len(results), 2)
        self.assertTrue(results["t1"].success)
        self.assertTrue(results["t2"].success)

        # Should complete in ~50ms (parallel), not 100ms (serial)
        self.assertLess(elapsed, 0.1)

    async def test_timeout_handling(self):
        """Test timeout handling."""
        async def slow_tool(args):
            await asyncio.sleep(5.0)
            return "result"

        executor = ParallelToolExecutor(
            tool_executors={"slow": slow_tool},
        )

        calls = [
            ToolCall("t1", "slow", {}, set(), timeout_ms=100),
        ]

        results = await executor.execute_batch(calls)

        # Should have timed out
        self.assertFalse(results["t1"].success)
        self.assertIn("Timeout", results["t1"].error)

    async def test_caching(self):
        """Test tool result caching."""
        call_count = 0

        async def cached_tool(args):
            nonlocal call_count
            call_count += 1
            return "result"

        executor = ParallelToolExecutor(
            tool_executors={"cached": cached_tool},
        )

        call = ToolCall("t1", "cached", {"arg": "value"}, set())

        # First execution
        results1 = await executor.execute_batch([call])
        self.assertEqual(call_count, 1)

        # Second execution - should use cache
        results2 = await executor.execute_batch([call])
        self.assertEqual(call_count, 1)
        self.assertTrue(results2["t1"].cache_hit)

    def test_metrics(self):
        """Test metrics collection."""
        metrics = self.executor.get_metrics()

        self.assertIn("total_tool_calls", metrics)
        self.assertIn("cache_hit_rate", metrics)
        self.assertIn("avg_call_latency_ms", metrics)

    async def test_dependency_ordering(self):
        """Test that dependencies are respected."""
        execution_order = []

        async def tool_a(args):
            execution_order.append("a")
            return "a"

        async def tool_b(args):
            execution_order.append("b")
            return "b"

        executor = ParallelToolExecutor(
            tool_executors={"a": tool_a, "b": tool_b},
        )

        calls = [
            ToolCall("t1", "a", {}, set()),
            ToolCall("t2", "b", {}, {"t1"}),  # depends on t1
        ]

        await executor.execute_batch(calls)

        # t1 should execute before t2
        self.assertLess(
            execution_order.index("a"),
            execution_order.index("b"),
        )


# Async test runner
def run_async_test(coro):
    """Helper to run async tests."""
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


# Add async tests to unittest
for test_class in [TestParallelToolExecutor]:
    for method_name in dir(test_class):
        if method_name.startswith("test_") and asyncio.iscoroutinefunction(
            getattr(test_class, method_name)
        ):
            original = getattr(test_class, method_name)
            setattr(
                test_class,
                method_name,
                lambda self, orig=original: run_async_test(orig(self)),
            )


if __name__ == "__main__":
    unittest.main()
