#!/usr/bin/env python3
"""
Validation script for lock-free tool dispatch components.

Runs comprehensive validation tests on all components to ensure
correctness, performance, and thread safety.

Usage:
    python tools/validate_lockfree.py
"""

import sys
import threading
import time
import concurrent.futures
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.lockfree_tool_queue import LockFreeToolQueue
from tools.waitfree_result_collector import (
    WaitFreeResultCollector,
    WaitFreeResultAggregator,
)
from tools.lockfree_schema_cache import LockFreeSchemaCacheManager
from tools.lockfree_dispatcher import LockFreeDispatcher, DispatchState


class ValidationTest:
    """Base class for validation tests."""

    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.error = None

    def run(self):
        """Run test and capture result."""
        try:
            self.test()
            self.passed = True
        except AssertionError as e:
            self.error = str(e)
            self.passed = False
        except Exception as e:
            self.error = f"Exception: {e}"
            self.passed = False

    def test(self):
        """Override to implement test logic."""
        raise NotImplementedError

    def report(self):
        """Print test result."""
        status = "✓ PASS" if self.passed else "✗ FAIL"
        print(f"  {status}: {self.name}")
        if self.error:
            print(f"         {self.error}")


# ============================================================================
# VALIDATION TESTS
# ============================================================================


class TestQueueSingleThread(ValidationTest):
    def test(self):
        queue = LockFreeToolQueue[int](capacity=128)
        for i in range(64):
            assert queue.enqueue(i), f"Enqueue {i} failed"
        for i in range(64):
            val = queue.dequeue()
            assert val == i, f"Expected {i}, got {val}"


class TestQueueConcurrentProducers(ValidationTest):
    def test(self):
        queue = LockFreeToolQueue[int](capacity=4096)
        produced = []
        produced_lock = threading.Lock()

        def producer(pid):
            for i in range(100):
                item = pid * 10000 + i
                if queue.enqueue(item):
                    with produced_lock:
                        produced.append(item)

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
            futures = [ex.submit(producer, p) for p in range(10)]
            for f in concurrent.futures.as_completed(futures):
                f.result()

        assert len(produced) == 1000, f"Produced {len(produced)}, expected 1000"


class TestQueueConcurrentConsumers(ValidationTest):
    def test(self):
        queue = LockFreeToolQueue[int](capacity=1024)
        # Pre-fill
        for i in range(512):
            queue.enqueue(i)

        consumed = []
        consumed_lock = threading.Lock()

        def consumer():
            while True:
                val = queue.dequeue()
                if val is None:
                    break
                with consumed_lock:
                    consumed.append(val)

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
            futures = [ex.submit(consumer) for _ in range(5)]
            for f in concurrent.futures.as_completed(futures):
                f.result()

        assert len(consumed) == 512, f"Consumed {len(consumed)}, expected 512"
        assert len(set(consumed)) == 512, "Duplicate items detected"


class TestQueueFull(ValidationTest):
    def test(self):
        queue = LockFreeToolQueue[int](capacity=8)
        for i in range(7):
            assert queue.enqueue(i), f"Enqueue {i} failed (should fit)"
        assert not queue.enqueue(100), "Should reject when full"


class TestResultCollectorBasic(ValidationTest):
    def test(self):
        collector = WaitFreeResultCollector()
        assert collector.record_result("t1", {"value": 1})
        assert not collector.record_result("t1", {"value": 2})
        assert collector.get_result("t1") == {"value": 1}


class TestResultCollectorConcurrent(ValidationTest):
    def test(self):
        collector = WaitFreeResultCollector()

        def recorder(tid):
            for i in range(50):
                collector.record_result(f"t_{tid}_{i}", {"v": i})

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
            futures = [ex.submit(recorder, t) for t in range(10)]
            for f in concurrent.futures.as_completed(futures):
                f.result()

        results = collector.get_all_results()
        assert len(results) == 500, f"Got {len(results)}, expected 500"


class TestResultCollectorWait(ValidationTest):
    def test(self):
        collector = WaitFreeResultCollector()

        def delayed_record():
            time.sleep(0.1)
            for i in range(5):
                collector.record_result(f"t_{i}", i)

        thread = threading.Thread(target=delayed_record, daemon=True)
        thread.start()

        start = time.time()
        results = collector.wait_all(count=5, timeout=2.0)
        elapsed = time.time() - start

        assert len(results) == 5, f"Got {len(results)}, expected 5"
        assert 0.09 < elapsed < 0.5, f"Wait time {elapsed} out of range"


class TestSchemaCacheRead(ValidationTest):
    def test(self):
        cache = LockFreeSchemaCacheManager()
        schema = {"name": "test", "params": {}}
        cache.add_tool("t1", schema)

        result = cache.get_schema("t1")
        assert result is not None
        assert result.schema == schema
        assert result.generation == 0


class TestSchemaCacheUpdate(ValidationTest):
    def test(self):
        cache = LockFreeSchemaCacheManager()
        cache.add_tool("t1", {"v": 1})
        assert cache.update_schema("t1", {"v": 2})

        result = cache.get_schema("t1")
        assert result.schema == {"v": 2}
        assert result.generation == 1


class TestSchemaCacheConcurrentReads(ValidationTest):
    def test(self):
        cache = LockFreeSchemaCacheManager()
        cache.add_tool("t1", {"data": list(range(100))})

        reads = []
        reads_lock = threading.Lock()

        def reader():
            for _ in range(100):
                cache.get_schema("t1")
                with reads_lock:
                    reads.append(1)

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
            futures = [ex.submit(reader) for _ in range(10)]
            for f in concurrent.futures.as_completed(futures):
                f.result()

        assert len(reads) == 1000, f"Completed {len(reads)}, expected 1000"


class TestDispatchBasic(ValidationTest):
    def test(self):
        dispatcher = LockFreeDispatcher()
        ctx = dispatcher.dispatch_tool("t1", "c1", {"v": 42})
        assert ctx.state == DispatchState.IDLE

        def exec(args):
            return args["v"] * 2

        success, result, error = dispatcher.execute_dispatch(ctx, exec)
        assert success
        assert result == 84
        assert ctx.state == DispatchState.COMPLETED


class TestDispatchConcurrent(ValidationTest):
    def test(self):
        dispatcher = LockFreeDispatcher()

        def dispatch_and_execute(tid):
            ctx = dispatcher.dispatch_tool(f"t_{tid}", f"c_{tid}", {"v": tid})
            success, result, error = dispatcher.execute_dispatch(
                ctx, lambda args: args["v"] * 2
            )
            assert success

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
            futures = [ex.submit(dispatch_and_execute, t) for t in range(50)]
            for f in concurrent.futures.as_completed(futures):
                f.result()

        stats = dispatcher.stats()
        assert stats["total_completed"] == 50, f"Completed {stats['total_completed']}"


class TestDispatchWait(ValidationTest):
    def test(self):
        dispatcher = LockFreeDispatcher()
        ctx = dispatcher.dispatch_tool("t1", "c1", {"v": 10})

        def delayed_exec(args):
            time.sleep(0.05)
            return args["v"] + 5

        thread = threading.Thread(
            target=lambda: dispatcher.execute_dispatch(ctx, delayed_exec),
            daemon=True,
        )
        thread.start()

        result = dispatcher.wait_completion("c1", timeout=1.0)
        assert result is not None
        success, value, error = result
        assert success
        assert value == 15


class TestDispatchCancel(ValidationTest):
    def test(self):
        dispatcher = LockFreeDispatcher()
        ctx = dispatcher.dispatch_tool("t1", "c1", {})

        assert dispatcher.cancel_dispatch("c1")
        assert ctx.state == DispatchState.CANCELLED

        # Idempotent
        assert dispatcher.cancel_dispatch("c1")


class TestIntegration(ValidationTest):
    def test(self):
        """Integration test: queue + dispatcher + collector."""
        queue = LockFreeToolQueue[dict](capacity=256)
        dispatcher = LockFreeDispatcher()
        collector = WaitFreeResultCollector()

        # Queue work
        for i in range(10):
            queue.enqueue({"id": i, "value": i * 10})

        # Process
        def processor():
            while True:
                item = queue.dequeue()
                if item is None:
                    break

                ctx = dispatcher.dispatch_tool(
                    "t", f"c_{item['id']}", item
                )

                def exec(args):
                    return args["value"] * 2

                success, result, error = dispatcher.execute_dispatch(ctx, exec)
                collector.record_result(
                    f"t_{item['id']}",
                    result,
                    status="completed" if success else "failed",
                )

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
            futures = [ex.submit(processor) for _ in range(5)]
            for f in concurrent.futures.as_completed(futures):
                f.result()

        results = collector.get_all_results()
        assert len(results) == 10, f"Got {len(results)}, expected 10"


# ============================================================================
# TEST RUNNER
# ============================================================================


def main():
    """Run all validation tests."""
    tests = [
        # Queue tests
        TestQueueSingleThread("Queue: single-thread FIFO"),
        TestQueueConcurrentProducers("Queue: concurrent producers"),
        TestQueueConcurrentConsumers("Queue: concurrent consumers"),
        TestQueueFull("Queue: full detection"),
        # Result collector tests
        TestResultCollectorBasic("ResultCollector: basic record/get"),
        TestResultCollectorConcurrent("ResultCollector: concurrent recording"),
        TestResultCollectorWait("ResultCollector: wait with timeout"),
        # Schema cache tests
        TestSchemaCacheRead("SchemaCache: read"),
        TestSchemaCacheUpdate("SchemaCache: update"),
        TestSchemaCacheConcurrentReads("SchemaCache: concurrent reads"),
        # Dispatcher tests
        TestDispatchBasic("Dispatcher: basic dispatch/execute"),
        TestDispatchConcurrent("Dispatcher: concurrent dispatches"),
        TestDispatchWait("Dispatcher: wait for completion"),
        TestDispatchCancel("Dispatcher: cancellation"),
        # Integration test
        TestIntegration("Integration: queue + dispatcher + collector"),
    ]

    print("\n" + "=" * 70)
    print("LOCK-FREE TOOL DISPATCH VALIDATION")
    print("=" * 70 + "\n")

    passed = 0
    failed = 0

    for test in tests:
        test.run()
        test.report()
        if test.passed:
            passed += 1
        else:
            failed += 1

    print("\n" + "=" * 70)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 70 + "\n")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
