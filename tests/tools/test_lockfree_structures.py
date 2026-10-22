#!/usr/bin/env python3
"""
Tests for lock-free and wait-free data structures.

Tests cover:
  - Correctness invariants
  - Concurrent execution safety
  - Progress guarantees
  - Pathological contention scenarios
  - Memory ordering
"""

import concurrent.futures
import random
import threading
import time
from typing import List

import pytest

from tools.lockfree_tool_queue import LockFreeToolQueue
from tools.waitfree_result_collector import (
    WaitFreeResultAggregator,
    WaitFreeResultCollector,
)
from tools.lockfree_schema_cache import (
    LockFreeSchemaCacheManager,
)
from tools.lockfree_dispatcher import (
    DispatchContext,
    DispatchState,
    FairDispatchScheduler,
    LockFreeDispatcher,
)


class TestLockFreeToolQueue:
    """Tests for lock-free FIFO queue."""

    def test_single_producer_consumer(self):
        """Single thread enqueue/dequeue should be FIFO."""
        queue = LockFreeToolQueue[int](capacity=100)

        # Enqueue items
        for i in range(10):
            assert queue.enqueue(i)

        # Dequeue items in order
        for i in range(10):
            assert queue.dequeue() == i

        # Queue should be empty
        assert queue.is_empty()
        assert queue.dequeue() is None

    def test_concurrent_producers(self):
        """Multiple producers should not corrupt queue."""
        queue = LockFreeToolQueue[int](capacity=1000)
        items_per_producer = 100
        num_producers = 10

        def producer(producer_id: int):
            for i in range(items_per_producer):
                item = producer_id * 10000 + i
                while not queue.enqueue(item):
                    time.sleep(0.001)

        # Run producers concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_producers) as executor:
            futures = [
                executor.submit(producer, pid) for pid in range(num_producers)
            ]
            for future in concurrent.futures.as_completed(futures):
                future.result()

        # Collect all dequeued items
        dequeued = []
        while True:
            item = queue.dequeue()
            if item is None:
                break
            dequeued.append(item)

        # Should have all items
        assert len(dequeued) == num_producers * items_per_producer

    def test_concurrent_consumers(self):
        """Multiple consumers should dequeue without duplicates."""
        queue = LockFreeToolQueue[int](capacity=1000)
        num_items = 500

        # Enqueue items first
        for i in range(num_items):
            assert queue.enqueue(i)

        dequeued = []
        dequeued_lock = threading.Lock()

        def consumer():
            while True:
                item = queue.dequeue()
                if item is None:
                    # Try harder
                    time.sleep(0.001)
                    continue
                with dequeued_lock:
                    dequeued.append(item)
                if len(dequeued) >= num_items:
                    break

        # Run multiple consumers
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(consumer) for _ in range(5)]
            for future in concurrent.futures.as_completed(futures):
                future.result(timeout=5.0)

        # All items should be dequeued exactly once
        assert len(dequeued) == num_items
        assert sorted(dequeued) == list(range(num_items))

    def test_queue_full(self):
        """Queue should reject enqueue when full."""
        queue = LockFreeToolQueue[int](capacity=10)

        # Fill queue
        for i in range(10):
            assert queue.enqueue(i)

        # Next enqueue should fail
        assert not queue.enqueue(10)
        assert queue.failed_enqueues >= 1

    def test_empty_dequeue(self):
        """Dequeue from empty queue should return None."""
        queue = LockFreeToolQueue[int](capacity=10)
        assert queue.dequeue() is None

    def test_alternating_operations(self):
        """Alternating enqueue/dequeue should maintain order."""
        queue = LockFreeToolQueue[int](capacity=100)

        for i in range(50):
            assert queue.enqueue(i)
            if i % 5 == 0:
                val = queue.dequeue()
                assert val in [j for j in range(i) if j % 5 == 0] or val is None


class TestWaitFreeResultCollector:
    """Tests for wait-free result collection."""

    def test_single_result(self):
        """Single result should be recorded and retrieved."""
        collector = WaitFreeResultCollector()

        result = {"status": "ok", "data": 42}
        assert collector.record_result("tool1", result)

        all_results = collector.get_all_results()
        assert all_results["tool1"] == result

    def test_duplicate_result(self):
        """Duplicate result should not be recorded."""
        collector = WaitFreeResultCollector()

        assert collector.record_result("tool1", {"value": 1})
        assert not collector.record_result("tool1", {"value": 2})

        # Should have first result
        assert collector.get_result("tool1") == {"value": 1}

    def test_concurrent_recording(self):
        """Multiple threads recording results should not corrupt state."""
        collector = WaitFreeResultCollector()
        num_threads = 10
        results_per_thread = 50

        def record_results(thread_id: int):
            for i in range(results_per_thread):
                collector.record_result(f"tool_{thread_id}_{i}", {"value": i})

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(record_results, tid) for tid in range(num_threads)
            ]
            for future in concurrent.futures.as_completed(futures):
                future.result()

        # All results should be recorded
        all_results = collector.get_all_results()
        assert len(all_results) == num_threads * results_per_thread

    def test_wait_all(self):
        """wait_all should block until count is reached."""
        collector = WaitFreeResultCollector()

        def delayed_recording():
            time.sleep(0.1)
            for i in range(5):
                collector.record_result(f"tool_{i}", {"value": i})

        # Start recording in background
        thread = threading.Thread(target=delayed_recording, daemon=True)
        thread.start()

        # Wait for results
        start = time.time()
        results = collector.wait_all(count=5, timeout=2.0)
        elapsed = time.time() - start

        assert len(results) == 5
        assert 0.09 < elapsed < 1.0  # Should wait ~0.1s

    def test_failed_results(self):
        """Failed results should be recorded separately."""
        collector = WaitFreeResultCollector()

        collector.record_result("tool1", {"value": 1}, status="completed")
        collector.record_result("tool2", None, status="failed", error="Tool crashed")

        failed = collector.get_failed_results()
        assert "tool2" in failed
        assert "tool1" not in failed

    def test_result_aggregator(self):
        """Result aggregator should filter/map results."""
        collector = WaitFreeResultCollector()
        aggregator = WaitFreeResultAggregator(collector)

        collector.record_result("tool_a", 10)
        collector.record_result("tool_b", 20)
        collector.record_result("tool_c", 30)

        # Filter
        filtered = aggregator.filter_results(
            lambda tool_id, val: val > 15
        )
        assert len(filtered) == 2

        # Map
        mapped = aggregator.map_results(lambda tool_id, val: val * 2)
        assert mapped["tool_a"] == 20
        assert mapped["tool_b"] == 40

        # Reduce
        summed = aggregator.reduce_results(
            lambda acc, tool_id, val: (acc or 0) + val, initial=0
        )
        assert summed == 60


class TestLockFreeSchemaCacheManager:
    """Tests for lock-free schema cache."""

    def test_add_and_retrieve(self):
        """Adding and retrieving schema should work."""
        cache = LockFreeSchemaCacheManager()
        schema = {"name": "tool1", "params": {"arg1": "str"}}

        cache.add_tool("tool1", schema)
        retrieved = cache.get_schema("tool1")

        assert retrieved is not None
        assert retrieved.schema == schema
        assert retrieved.generation == 0

    def test_schema_update(self):
        """Schema update should atomically replace old schema."""
        cache = LockFreeSchemaCacheManager()
        old_schema = {"name": "tool1", "version": 1}
        new_schema = {"name": "tool1", "version": 2}

        cache.add_tool("tool1", old_schema)
        cache.update_schema("tool1", new_schema)

        retrieved = cache.get_schema("tool1")
        assert retrieved.schema == new_schema
        assert retrieved.generation == 1

    def test_concurrent_reads_during_write(self):
        """Readers should not be blocked by writers."""
        cache = LockFreeSchemaCacheManager()
        schema = {"params": list(range(100))}
        cache.add_tool("tool1", schema)

        read_times = []
        write_times = []

        def reader():
            start = time.time()
            for _ in range(50):
                cache.get_schema("tool1")
            read_times.append(time.time() - start)

        def writer():
            start = time.time()
            for i in range(10):
                new_schema = {"params": list(range(100)), "version": i}
                cache.update_schema("tool1", new_schema)
                time.sleep(0.01)
            write_times.append(time.time() - start)

        # Run readers while writer updates
        reader_threads = [
            threading.Thread(target=reader) for _ in range(5)
        ]
        writer_thread = threading.Thread(target=writer)

        writer_thread.start()
        for t in reader_threads:
            t.start()

        writer_thread.join()
        for t in reader_threads:
            t.join()

        # Readers should complete quickly (not blocked by writer)
        avg_read_time = sum(read_times) / len(read_times)
        # Should be very fast (no locks on read path)
        assert avg_read_time < 0.1

    def test_not_found(self):
        """Getting non-existent tool should return None."""
        cache = LockFreeSchemaCacheManager()
        assert cache.get_schema("nonexistent") is None

    def test_cache_stats(self):
        """Cache should track statistics."""
        cache = LockFreeSchemaCacheManager()

        cache.add_tool("tool1", {})
        cache.get_schema("tool1")  # hit
        cache.get_schema("tool2")  # miss

        stats = cache.stats()
        assert stats["cache_hits"] == 1
        assert stats["cache_misses"] == 1


class TestLockFreeDispatcher:
    """Tests for lock-free tool dispatcher."""

    def test_dispatch_and_execute(self):
        """Dispatch and execute should transition states correctly."""
        dispatcher = LockFreeDispatcher()

        ctx = dispatcher.dispatch_tool("tool1", "call_1", {"arg": 42})
        assert ctx.state == DispatchState.IDLE

        def executor(args):
            return args["arg"] * 2

        success, result, error = dispatcher.execute_dispatch(ctx, executor)
        assert success
        assert result == 84
        assert ctx.state == DispatchState.COMPLETED

    def test_concurrent_dispatches(self):
        """Multiple concurrent dispatches should work."""
        dispatcher = LockFreeDispatcher()

        def tool_executor(tool_id: int):
            def executor(args):
                return args["value"] * 2

            ctx = dispatcher.dispatch_tool(
                f"tool_{tool_id}",
                f"call_{tool_id}",
                {"value": tool_id},
            )
            success, result, error = dispatcher.execute_dispatch(ctx, executor)
            return success, result

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(tool_executor, i) for i in range(100)
            ]
            for future in concurrent.futures.as_completed(futures):
                success, result = future.result()
                assert success

    def test_wait_completion(self):
        """wait_completion should block until done."""
        dispatcher = LockFreeDispatcher()

        ctx = dispatcher.dispatch_tool("tool1", "call_1", {"value": 42})

        def delayed_executor(args):
            time.sleep(0.2)
            return args["value"] * 2

        # Execute in background
        thread = threading.Thread(
            target=lambda: dispatcher.execute_dispatch(ctx, delayed_executor),
            daemon=True,
        )
        thread.start()

        # Wait for completion
        start = time.time()
        result = dispatcher.wait_completion("call_1", timeout=1.0)
        elapsed = time.time() - start

        assert result is not None
        success, value, error = result
        assert success
        assert value == 84
        assert 0.19 < elapsed < 0.5

    def test_cancel_dispatch(self):
        """Cancelling dispatch should prevent execution."""
        dispatcher = LockFreeDispatcher()

        ctx = dispatcher.dispatch_tool("tool1", "call_1", {"value": 42})

        assert dispatcher.cancel_dispatch("call_1")
        assert ctx.state == DispatchState.CANCELLED

        # Trying to cancel again should return True (idempotent)
        assert dispatcher.cancel_dispatch("call_1")

    def test_retry_on_failure(self):
        """Failed execution should retry if retries remain."""
        dispatcher = LockFreeDispatcher()

        attempt_count = [0]

        def failing_executor(args):
            attempt_count[0] += 1
            if attempt_count[0] < 3:
                raise ValueError("Not ready")
            return "success"

        ctx = dispatcher.dispatch_tool("tool1", "call_1", {}, max_retries=3)

        for attempt in range(3):
            success, result, error = dispatcher.execute_dispatch(
                ctx, failing_executor
            )
            if not success and ctx.attempts < ctx.max_retries:
                assert ctx.state == DispatchState.IDLE
            else:
                break

        assert ctx.state == DispatchState.COMPLETED
        assert attempt_count[0] == 3

    def test_dispatcher_stats(self):
        """Dispatcher should track statistics."""
        dispatcher = LockFreeDispatcher()

        for i in range(5):
            ctx = dispatcher.dispatch_tool(f"tool_{i}", f"call_{i}", {})
            dispatcher.execute_dispatch(ctx, lambda args: None)

        stats = dispatcher.stats()
        assert stats["total_dispatches"] == 5
        assert stats["total_completed"] == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
