"""Tests for ultra-fast inference execution."""

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, Mock, patch

from agent.execution.fast_inference import (
    ContextPruner,
    FastInferenceEngine,
    FastInferenceResult,
    InferenceCache,
    TokenReduction,
)


class TestInferenceCache(unittest.TestCase):
    """Test response caching."""

    def setUp(self):
        self.cache = InferenceCache(max_entries=10, ttl_seconds=3600)

    def test_cache_store_and_retrieve(self):
        """Test storing and retrieving cached responses."""
        messages = [{"role": "user", "content": "test"}]
        response = "test response"

        self.cache.store(messages, response, "test-model", 100.0)

        retrieved = self.cache.lookup(messages)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.response, response)
        self.assertEqual(retrieved.model_used, "test-model")

    def test_cache_miss_tracking(self):
        """Test cache miss tracking."""
        messages = [{"role": "user", "content": "test"}]

        self.cache.lookup(messages)
        self.assertEqual(self.cache.misses, 1)
        self.assertEqual(self.cache.hits, 0)

    def test_cache_hit_tracking(self):
        """Test cache hit tracking."""
        messages = [{"role": "user", "content": "test"}]
        self.cache.store(messages, "response", "model", 100.0)

        self.cache.lookup(messages)
        self.assertEqual(self.cache.hits, 1)

    def test_cache_ttl_expiration(self):
        """Test cache TTL expiration."""
        cache = InferenceCache(max_entries=10, ttl_seconds=0)
        messages = [{"role": "user", "content": "test"}]

        cache.store(messages, "response", "model", 100.0)
        import time
        time.sleep(0.01)
        result = cache.lookup(messages)

        self.assertIsNone(result)

    def test_cache_lru_eviction(self):
        """Test LRU eviction when max entries exceeded."""
        cache = InferenceCache(max_entries=2, ttl_seconds=3600)

        for i in range(3):
            msg = [{"role": "user", "content": f"test{i}"}]
            cache.store(msg, f"response{i}", "model", 100.0)

        self.assertLessEqual(len(cache.cache), 2)

    def test_hit_rate_calculation(self):
        """Test hit rate calculation."""
        messages1 = [{"role": "user", "content": "test1"}]
        messages2 = [{"role": "user", "content": "test2"}]

        self.cache.store(messages1, "response1", "model", 100.0)

        # 1 hit
        self.cache.lookup(messages1)
        # 1 miss
        self.cache.lookup(messages2)

        self.assertAlmostEqual(self.cache.hit_rate(), 0.5, places=2)


class TestContextPruner(unittest.TestCase):
    """Test context pruning for token reduction."""

    def test_estimate_tokens(self):
        """Test token estimation."""
        content = "a" * 100
        tokens = ContextPruner.estimate_tokens(content)
        self.assertAlmostEqual(tokens, 25, delta=5)

    def test_prune_messages(self):
        """Test message pruning."""
        messages = [
            {"role": "user", "content": f"message{i}"}
            for i in range(30)
        ]

        pruned, reduction = ContextPruner.prune_messages(messages, 0.2)

        self.assertLess(len(pruned), len(messages))
        self.assertEqual(
            reduction.original_token_count
            - reduction.reduced_token_count,
            reduction.savings,
        )
        self.assertGreater(reduction.reduction_percent, 0)

    def test_compress_content(self):
        """Test content compression."""
        long_content = "x" * 1000
        compressed = ContextPruner.compress_content(
            long_content, max_length=100
        )

        self.assertLessEqual(len(compressed), 112)  # 100 + "[truncated]"
        self.assertIn("[truncated]", compressed)

    def test_preserve_tool_calls(self):
        """Test that tool calls are preserved during pruning."""
        messages = [
            {"role": "user", "content": "user message"},
            {
                "role": "assistant",
                "content": json.dumps({"tool_use": "test_tool"}),
            },
            {"role": "user", "content": f"msg{i}"} for i in range(20)
        ]

        pruned, _ = ContextPruner.prune_messages(messages, 0.3)

        # Tool call should be preserved
        tool_call_preserved = any(
            "tool_use" in m.get("content", "")
            for m in pruned
        )
        self.assertTrue(tool_call_preserved)


class TestFastInferenceResult(unittest.TestCase):
    """Test inference result metrics."""

    def test_is_fast_detection(self):
        """Test fast response detection."""
        fast_result = FastInferenceResult(
            response="test",
            model="fast",
            latency_ms=100,
            cache_hit=False,
            used_pruning=False,
        )
        self.assertTrue(fast_result.is_fast)

        slow_result = FastInferenceResult(
            response="test",
            model="capable",
            latency_ms=1000,
            cache_hit=False,
            used_pruning=False,
        )
        self.assertFalse(slow_result.is_fast)


class TestParallelInference(unittest.TestCase):
    """Test parallel inference execution."""

    def setUp(self):
        from agent.execution.fast_inference import ParallelInference
        self.executor = ParallelInference(timeout_ms=200)

    def test_parallel_inference_fast_wins(self):
        """Test that fast model wins when successful."""
        async def fast_fn(msg):
            await asyncio.sleep(0.05)
            return "fast response"

        async def capable_fn(msg):
            await asyncio.sleep(0.5)
            return "capable response"

        async def run_test():
            result = await self.executor.execute_parallel(
                fast_fn, capable_fn, [{"role": "user", "content": "test"}]
            )
            return result

        result = asyncio.run(run_test())
        self.assertEqual(result.model, "fast")

    def test_parallel_inference_timeout(self):
        """Test fallback when fast model times out."""
        async def slow_fast_fn(msg):
            await asyncio.sleep(1.0)
            return "fast response"

        async def capable_fn(msg):
            await asyncio.sleep(0.05)
            return "capable response"

        async def run_test():
            result = await self.executor.execute_parallel(
                slow_fast_fn, capable_fn, [
                    {"role": "user", "content": "test"}
                ]
            )
            return result

        result = asyncio.run(run_test())
        self.assertEqual(result.model, "capable")


class TestFastInferenceEngine(unittest.TestCase):
    """Test the complete fast inference engine."""

    def setUp(self):
        self.engine = FastInferenceEngine(cache_size=100)

    async def test_inference_with_caching(self):
        """Test inference with caching enabled."""
        call_count = 0

        async def fast_fn(msg):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            return "response"

        async def capable_fn(msg):
            await asyncio.sleep(0.1)
            return "response"

        messages = [{"role": "user", "content": "test"}]

        # First call - cache miss
        result1 = await self.engine.infer(
            messages,
            fast_fn,
            capable_fn,
            enable_cache=True,
        )
        self.assertFalse(result1.cache_hit)

        # Second call - should hit cache
        result2 = await self.engine.infer(
            messages,
            fast_fn,
            capable_fn,
            enable_cache=True,
        )
        self.assertTrue(result2.cache_hit)

        # Should not call fast_fn twice due to caching
        self.assertEqual(call_count, 1)

    def test_metrics_collection(self):
        """Test that metrics are collected correctly."""
        async def fast_fn(msg):
            await asyncio.sleep(0.01)
            return "response"

        async def capable_fn(msg):
            return "response"

        async def run_test():
            messages = [{"role": "user", "content": "test"}]
            await self.engine.infer(
                messages, fast_fn, capable_fn,
                enable_cache=False
            )

        asyncio.run(run_test())

        metrics = self.engine.get_metrics()
        self.assertEqual(metrics["total_calls"], 1)
        self.assertGreater(metrics["avg_latency_ms"], 0)


if __name__ == "__main__":
    unittest.main()
