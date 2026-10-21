#!/usr/bin/env python3
"""
Benchmark suite for lock-free tool dispatch structures.

Measures:
  - Throughput (operations per second)
  - Latency (p50, p99, p99.9)
  - Contention impact
  - Memory usage
  - Scalability (ops/thread)

Usage:
    python tools/bench_lockfree_dispatch.py
"""

import concurrent.futures
import statistics
import threading
import time
from dataclasses import dataclass
from typing import Callable, List

from tools.lockfree_tool_queue import LockFreeToolQueue
from tools.waitfree_result_collector import WaitFreeResultCollector
from tools.lockfree_schema_cache import LockFreeSchemaCacheManager
from tools.lockfree_dispatcher import LockFreeDispatcher


@dataclass
class BenchmarkResult:
    """Single benchmark result."""

    name: str
    duration_seconds: float
    operations: int
    throughput: float  # ops/sec
    latencies: List[float]

    @property
    def p50(self) -> float:
        """Median latency."""
        if not self.latencies:
            return 0
        return statistics.median(self.latencies)

    @property
    def p99(self) -> float:
        """99th percentile latency."""
        if not self.latencies:
            return 0
        sorted_latencies = sorted(self.latencies)
        idx = int(len(sorted_latencies) * 0.99)
        return sorted_latencies[min(idx, len(sorted_latencies) - 1)]

    @property
    def p999(self) -> float:
        """99.9th percentile latency."""
        if not self.latencies:
            return 0
        sorted_latencies = sorted(self.latencies)
        idx = int(len(sorted_latencies) * 0.999)
        return sorted_latencies[min(idx, len(sorted_latencies) - 1)]

    def __str__(self):
        return (
            f"{self.name:40s} | "
            f"{self.throughput:15,.0f} ops/sec | "
            f"p50={self.p50*1e6:8.2f}µs | "
            f"p99={self.p99*1e6:8.2f}µs | "
            f"p999={self.p999*1e6:8.2f}µs"
        )


class LockFreeBenchmark:
    """Benchmark suite for lock-free structures."""

    def bench_queue_enqueue_single_thread(
        self, iterations: int = 100000
    ) -> BenchmarkResult:
        """Benchmark single-thread enqueue."""
        queue = LockFreeToolQueue[int](capacity=200000)
        latencies = []

        start = time.perf_counter()
        for i in range(iterations):
            t0 = time.perf_counter()
            queue.enqueue(i)
            t1 = time.perf_counter()
            latencies.append(t1 - t0)
        end = time.perf_counter()

        return BenchmarkResult(
            name="Queue: single-thread enqueue",
            duration_seconds=end - start,
            operations=iterations,
            throughput=iterations / (end - start),
            latencies=latencies,
        )

    def bench_queue_dequeue_single_thread(
        self, iterations: int = 100000
    ) -> BenchmarkResult:
        """Benchmark single-thread dequeue."""
        queue = LockFreeToolQueue[int](capacity=200000)

        # Enqueue first
        for i in range(iterations):
            queue.enqueue(i)

        latencies = []
        start = time.perf_counter()
        for i in range(iterations):
            t0 = time.perf_counter()
            queue.dequeue()
            t1 = time.perf_counter()
            latencies.append(t1 - t0)
        end = time.perf_counter()

        return BenchmarkResult(
            name="Queue: single-thread dequeue",
            duration_seconds=end - start,
            operations=iterations,
            throughput=iterations / (end - start),
            latencies=latencies,
        )

    def bench_queue_concurrent_producers(
        self, num_threads: int = 10, items_per_thread: int = 10000
    ) -> BenchmarkResult:
        """Benchmark concurrent producers."""
        queue = LockFreeToolQueue[int](capacity=200000)
        total_ops = num_threads * items_per_thread
        latencies = []
        latencies_lock = threading.Lock()

        def producer(producer_id: int):
            local_latencies = []
            for i in range(items_per_thread):
                item = producer_id * 100000 + i
                t0 = time.perf_counter()
                while not queue.enqueue(item):
                    pass  # Busy wait on full
                t1 = time.perf_counter()
                local_latencies.append(t1 - t0)

            with latencies_lock:
                latencies.extend(local_latencies)

        start = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(producer, pid) for pid in range(num_threads)
            ]
            for future in concurrent.futures.as_completed(futures):
                future.result()
        end = time.perf_counter()

        return BenchmarkResult(
            name=f"Queue: {num_threads} concurrent producers",
            duration_seconds=end - start,
            operations=total_ops,
            throughput=total_ops / (end - start),
            latencies=latencies,
        )

    def bench_queue_concurrent_consumers(
        self, num_threads: int = 10, items: int = 50000
    ) -> BenchmarkResult:
        """Benchmark concurrent consumers."""
        queue = LockFreeToolQueue[int](capacity=200000)

        # Pre-fill queue
        for i in range(items):
            queue.enqueue(i)

        latencies = []
        latencies_lock = threading.Lock()

        def consumer():
            local_latencies = []
            while True:
                t0 = time.perf_counter()
                item = queue.dequeue()
                t1 = time.perf_counter()

                if item is not None:
                    local_latencies.append(t1 - t0)
                else:
                    # Queue empty
                    break

            with latencies_lock:
                latencies.extend(local_latencies)

        start = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(consumer) for _ in range(num_threads)]
            for future in concurrent.futures.as_completed(futures):
                future.result()
        end = time.perf_counter()

        return BenchmarkResult(
            name=f"Queue: {num_threads} concurrent consumers",
            duration_seconds=end - start,
            operations=items,
            throughput=items / (end - start),
            latencies=latencies,
        )

    def bench_result_collector_single_thread(
        self, iterations: int = 100000
    ) -> BenchmarkResult:
        """Benchmark single-thread result recording."""
        collector = WaitFreeResultCollector()
        latencies = []

        start = time.perf_counter()
        for i in range(iterations):
            t0 = time.perf_counter()
            collector.record_result(f"tool_{i}", {"value": i})
            t1 = time.perf_counter()
            latencies.append(t1 - t0)
        end = time.perf_counter()

        return BenchmarkResult(
            name="ResultCollector: single-thread record",
            duration_seconds=end - start,
            operations=iterations,
            throughput=iterations / (end - start),
            latencies=latencies,
        )

    def bench_result_collector_concurrent(
        self, num_threads: int = 10, records_per_thread: int = 10000
    ) -> BenchmarkResult:
        """Benchmark concurrent result recording."""
        collector = WaitFreeResultCollector()
        total_ops = num_threads * records_per_thread
        latencies = []
        latencies_lock = threading.Lock()

        def recorder(thread_id: int):
            local_latencies = []
            for i in range(records_per_thread):
                t0 = time.perf_counter()
                collector.record_result(f"tool_{thread_id}_{i}", {"value": i})
                t1 = time.perf_counter()
                local_latencies.append(t1 - t0)

            with latencies_lock:
                latencies.extend(local_latencies)

        start = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(recorder, tid) for tid in range(num_threads)
            ]
            for future in concurrent.futures.as_completed(futures):
                future.result()
        end = time.perf_counter()

        return BenchmarkResult(
            name=f"ResultCollector: {num_threads} concurrent recorders",
            duration_seconds=end - start,
            operations=total_ops,
            throughput=total_ops / (end - start),
            latencies=latencies,
        )

    def bench_schema_cache_reads(
        self, num_threads: int = 20, reads_per_thread: int = 10000
    ) -> BenchmarkResult:
        """Benchmark concurrent schema reads (lock-free path)."""
        cache = LockFreeSchemaCacheManager()
        cache.add_tool("tool1", {"params": list(range(100))})
        cache.add_tool("tool2", {"params": list(range(100))})

        total_ops = num_threads * reads_per_thread
        latencies = []
        latencies_lock = threading.Lock()

        def reader(thread_id: int):
            local_latencies = []
            for i in range(reads_per_thread):
                tool_id = f"tool{(i % 2) + 1}"
                t0 = time.perf_counter()
                cache.get_schema(tool_id)
                t1 = time.perf_counter()
                local_latencies.append(t1 - t0)

            with latencies_lock:
                latencies.extend(local_latencies)

        start = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(reader, tid) for tid in range(num_threads)
            ]
            for future in concurrent.futures.as_completed(futures):
                future.result()
        end = time.perf_counter()

        return BenchmarkResult(
            name=f"SchemaCache: {num_threads} concurrent readers",
            duration_seconds=end - start,
            operations=total_ops,
            throughput=total_ops / (end - start),
            latencies=latencies,
        )

    def bench_dispatcher_dispatch(
        self, num_dispatches: int = 100000
    ) -> BenchmarkResult:
        """Benchmark dispatch operation."""
        dispatcher = LockFreeDispatcher()
        latencies = []

        start = time.perf_counter()
        for i in range(num_dispatches):
            t0 = time.perf_counter()
            dispatcher.dispatch_tool(f"tool_{i}", f"call_{i}", {})
            t1 = time.perf_counter()
            latencies.append(t1 - t0)
        end = time.perf_counter()

        return BenchmarkResult(
            name="Dispatcher: dispatch",
            duration_seconds=end - start,
            operations=num_dispatches,
            throughput=num_dispatches / (end - start),
            latencies=latencies,
        )

    def run_all(self):
        """Run all benchmarks and print results."""
        print("\n" + "=" * 120)
        print("LOCK-FREE TOOL DISPATCH BENCHMARK")
        print("=" * 120 + "\n")

        benchmarks = [
            ("Queue Performance", [
                self.bench_queue_enqueue_single_thread,
                self.bench_queue_dequeue_single_thread,
                lambda: self.bench_queue_concurrent_producers(10, 10000),
                lambda: self.bench_queue_concurrent_consumers(10, 50000),
            ]),
            ("Result Collector Performance", [
                self.bench_result_collector_single_thread,
                lambda: self.bench_result_collector_concurrent(10, 10000),
            ]),
            ("Schema Cache Performance", [
                lambda: self.bench_schema_cache_reads(20, 10000),
            ]),
            ("Dispatcher Performance", [
                self.bench_dispatcher_dispatch,
            ]),
        ]

        all_results = []
        for category, benches in benchmarks:
            print(f"\n{category}:")
            print("-" * 120)

            for bench_func in benches:
                result = bench_func()
                all_results.append(result)
                print(result)

        print("\n" + "=" * 120)
        print("SUMMARY")
        print("=" * 120 + "\n")

        # Calculate aggregate stats
        total_throughput = sum(r.throughput for r in all_results)
        avg_p50 = statistics.mean(r.p50 for r in all_results)
        avg_p99 = statistics.mean(r.p99 for r in all_results)

        print(f"Total combined throughput: {total_throughput:,.0f} ops/sec")
        print(f"Average p50 latency: {avg_p50*1e6:.2f}µs")
        print(f"Average p99 latency: {avg_p99*1e6:.2f}µs")
        print(f"\nBenchmarks run: {len(all_results)}")
        print(
            f"Total operations: {sum(r.operations for r in all_results):,.0f}"
        )


if __name__ == "__main__":
    bench = LockFreeBenchmark()
    bench.run_all()
