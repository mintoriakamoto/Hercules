#!/usr/bin/env python3
"""
Phase 3 Tool Acceleration Benchmark Suite

Validates distributed dispatch infrastructure:
1. Consistent hash ring performance and distribution
2. Load balancing across dispatch nodes
3. Batching overhead reduction
4. Fault tolerance and failover
5. Schema cache efficiency (zero-copy)
6. Distributed consensus verification
7. End-to-end round-trip scaling to 1B+ calls/sec

Execution: python -m tools.bench_phase3 [--profile] [--verbose] [--num-calls N]
"""

import json
import logging
import sys
import time
import gc
import psutil
import random
import threading
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from collections import defaultdict, deque
import statistics

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.distributed_dispatch import (
    DistributedDispatcher,
    ToolCallRequest,
    ToolCallResult,
)
from tools.tool_pool import ToolPoolCluster, PoolHealthStatus
from tools.distributed_cache import get_schema_cache
from agent.consensus.distributed import get_distributed_verifier

logger = logging.getLogger(__name__)


class BenchmarkTimer:
    """Context manager for precise timing and memory measurements."""

    def __init__(self, name: str = ""):
        self.name = name
        self.start_time = None
        self.elapsed_ms = 0.0
        self.start_memory = 0
        self.end_memory = 0

    def __enter__(self):
        gc.collect()
        self.start_memory = psutil.Process().memory_info().rss
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.elapsed_ms = (time.perf_counter() - self.start_time) * 1000.0
        self.end_memory = psutil.Process().memory_info().rss

    @property
    def memory_delta_mb(self) -> float:
        return (self.end_memory - self.start_memory) / (1024 * 1024)


class Phase3Benchmarks:
    """Complete benchmark suite for Phase 3 distributed dispatch."""

    def __init__(self, verbose: bool = False, num_calls: int = 10000):
        self.verbose = verbose
        self.num_calls = num_calls
        self.results = defaultdict(dict)

        # Initialize infrastructure
        self.dispatcher = DistributedDispatcher()
        self.pool_cluster = ToolPoolCluster(pool_size=10)
        self.schema_cache = get_schema_cache()
        self.verifier = get_distributed_verifier()

        # Add dispatch nodes
        self._setup_nodes()

    def _setup_nodes(self) -> None:
        """Set up test dispatch cluster."""
        nodes = [
            ("node-1", "localhost", 9001, 1.0),
            ("node-2", "localhost", 9002, 1.0),
            ("node-3", "localhost", 9003, 1.0),
            ("node-4", "localhost", 9004, 0.8),  # Lighter weight
            ("node-5", "localhost", 9005, 1.2),  # Heavier weight
        ]

        for node_id, addr, port, weight in nodes:
            self.dispatcher.add_node(node_id, addr, port, weight)
            self.pool_cluster.add_pool(node_id, addr, port)

        self._log(f"Set up {len(nodes)} dispatch nodes")

    def _log(self, msg: str, level: str = "INFO"):
        """Print benchmark messages."""
        if self.verbose or level in ("ERROR", "RESULT"):
            timestamp = time.strftime("%H:%M:%S")
            print(f"[{timestamp}] {level:8s} {msg}", flush=True)

    # =========================================================================
    # BENCHMARK: Hash Ring Distribution
    # =========================================================================

    def benchmark_hash_ring_distribution(self) -> Dict[str, Any]:
        """Verify consistent hash ring distributes tools evenly.

        Measures:
          - Distribution uniformity (StdDev of tool assignments)
          - Lookup latency
          - Rebalancing cost when nodes fail
        """
        self._log("Benchmarking hash ring distribution...")

        tools = [f"tool_{i}" for i in range(100)]
        distribution = defaultdict(int)

        with BenchmarkTimer("hash_ring_distribution") as timer:
            for tool_name in tools * 100:  # 10k lookups
                args_hash = f"default_args"
                nodes = self.dispatcher.hash_ring.get_nodes(tool_name, args_hash, 1)

                if nodes:
                    distribution[nodes[0].node_id] += 1

        # Calculate distribution uniformity
        counts = list(distribution.values())
        mean = statistics.mean(counts)
        stdev = statistics.stdev(counts) if len(counts) > 1 else 0
        uniformity = stdev / mean if mean > 0 else 0

        return {
            'total_lookups': 10000,
            'lookup_latency_ms': timer.elapsed_ms / 10000,
            'distribution_stdev': stdev,
            'distribution_uniformity_pct': uniformity * 100,
            'target_uniformity_pct': 5.0,  # Desired StdDev/Mean
        }

    # =========================================================================
    # BENCHMARK: Load Balancing
    # =========================================================================

    def benchmark_load_balancing(self) -> Dict[str, Any]:
        """Measure load distribution across nodes.

        Simulates concurrent requests and verifies even distribution.
        """
        self._log("Benchmarking load balancing...")

        requests = []
        for i in range(self.num_calls):
            requests.append(ToolCallRequest(
                tool_name=f"tool_{i % 20}",
                args={"index": i},
                request_id=f"req_{i}",
            ))

        loads = defaultdict(int)

        with BenchmarkTimer("load_balancing") as timer:
            for req in requests:
                args_hash = json.dumps(req.args, sort_keys=True, default=str)
                nodes = self.dispatcher.hash_ring.get_nodes(
                    req.tool_name, args_hash, 1
                )

                if nodes:
                    loads[nodes[0].node_id] += 1

        load_values = list(loads.values())
        avg_load = statistics.mean(load_values)
        load_stdev = statistics.stdev(load_values) if len(load_values) > 1 else 0

        return {
            'total_requests': self.num_calls,
            'routing_latency_ms': timer.elapsed_ms / self.num_calls,
            'avg_load_per_node': avg_load,
            'load_stdev': load_stdev,
            'load_uniformity_pct': (load_stdev / avg_load * 100) if avg_load > 0 else 0,
            'loads_by_node': dict(loads),
        }

    # =========================================================================
    # BENCHMARK: Batching Overhead Reduction
    # =========================================================================

    def benchmark_batching_efficiency(self) -> Dict[str, Any]:
        """Measure overhead reduction from request batching.

        Compares:
          - Single requests (no batching)
          - Batched requests (10, 50, 100 per batch)
        """
        self._log("Benchmarking batching efficiency...")

        batch_sizes = [1, 10, 50, 100]
        results = {}

        for batch_size in batch_sizes:
            requests = [
                ToolCallRequest(
                    tool_name=f"tool_{i % 20}",
                    args={"index": i},
                    request_id=f"req_{i}",
                )
                for i in range(min(1000, self.num_calls))
            ]

            with BenchmarkTimer(f"batching_size_{batch_size}") as timer:
                # Simulate batching
                for i in range(0, len(requests), batch_size):
                    batch = requests[i:i+batch_size]
                    # Dispatch batch
                    self.dispatcher.dispatch_batch(batch)

            throughput = len(requests) / (timer.elapsed_ms / 1000) if timer.elapsed_ms > 0 else 0

            results[f"batch_size_{batch_size}"] = {
                'num_requests': len(requests),
                'total_time_ms': timer.elapsed_ms,
                'throughput_calls_per_sec': throughput,
                'latency_per_call_ms': timer.elapsed_ms / len(requests),
            }

        return results

    # =========================================================================
    # BENCHMARK: Schema Cache Performance
    # =========================================================================

    def benchmark_schema_cache(self) -> Dict[str, Any]:
        """Measure zero-copy schema cache performance.

        Validates:
          - Cache hit rate
          - Zero-copy access latency
          - Generation-based invalidation
        """
        self._log("Benchmarking schema cache...")

        # Pre-populate cache
        schemas = {}
        for i in range(50):
            tool_name = f"tool_{i}"
            schema = {
                'name': tool_name,
                'description': f'Tool {i}',
                'parameters': {'type': 'object', 'properties': {}},
            }
            schemas[tool_name] = schema
            self.schema_cache.put(tool_name, schema)

        # Measure cache access
        with BenchmarkTimer("schema_cache_access") as timer:
            for _ in range(10000):
                tool_name = f"tool_{random.randint(0, 49)}"
                schema = self.schema_cache.get(tool_name)

        stats = self.schema_cache.get_stats()

        return {
            'cached_schemas': stats['num_cached'],
            'total_accesses': 10000,
            'cache_hits': stats['hits'],
            'cache_misses': stats['misses'],
            'hit_rate_pct': stats['hit_rate_percent'],
            'access_latency_us': (timer.elapsed_ms / 10000) * 1000,
            'generation': stats['generation'],
        }

    # =========================================================================
    # BENCHMARK: Distributed Consensus
    # =========================================================================

    def benchmark_distributed_consensus(self) -> Dict[str, Any]:
        """Measure distributed consensus verification performance.

        Tests:
          - Verification latency
          - Quorum agreement
          - Proof caching
        """
        self._log("Benchmarking distributed consensus...")

        # Simulate node results
        verifications = []

        with BenchmarkTimer("consensus_verification") as timer:
            for i in range(1000):
                tool_name = f"tool_{i % 10}"
                args = {"index": i}

                # Simulate results from 3 nodes
                node_results = {
                    "node-1": {"result": "ok", "data": i},
                    "node-2": {"result": "ok", "data": i},
                    "node-3": {"result": "ok", "data": i},
                }

                verification = self.verifier.verify_distributed(
                    tool_name, args, node_results
                )
                verifications.append(verification)

        stats = self.verifier.get_stats()

        return {
            'total_verifications': len(verifications),
            'verification_latency_ms': timer.elapsed_ms / len(verifications),
            'successful_verifications': stats['successful_verifications'],
            'failed_verifications': stats['failed_verifications'],
            'cached_hits': stats['cached_hits'],
        }

    # =========================================================================
    # BENCHMARK: Fault Tolerance
    # =========================================================================

    def benchmark_fault_tolerance(self) -> Dict[str, Any]:
        """Measure failover and recovery behavior.

        Tests:
          - Failover latency
          - Recovery time
          - Request success rate during failures
        """
        self._log("Benchmarking fault tolerance...")

        results = {
            'single_node_failure': self._test_node_failure(),
            'multi_node_failure': self._test_multiple_failures(),
            'recovery': self._test_recovery(),
        }

        return results

    def _test_node_failure(self) -> Dict[str, Any]:
        """Test single node failure."""
        # Mark a node as unhealthy
        node = list(self.dispatcher.nodes.values())[0]
        original_healthy = node.healthy
        node.healthy = False

        requests = [
            ToolCallRequest(
                tool_name=f"tool_{i % 10}",
                args={"index": i},
                request_id=f"req_{i}",
            )
            for i in range(100)
        ]

        successful = 0

        with BenchmarkTimer("single_node_failure") as timer:
            for req in requests:
                result = self.dispatcher.dispatch_call(req)
                if result.success:
                    successful += 1

        node.healthy = original_healthy  # Restore

        return {
            'total_requests': len(requests),
            'successful': successful,
            'success_rate_pct': (successful / len(requests)) * 100,
            'failover_latency_ms': timer.elapsed_ms / len(requests),
        }

    def _test_multiple_failures(self) -> Dict[str, Any]:
        """Test multiple node failures."""
        # Mark 2 nodes as unhealthy
        nodes = list(self.dispatcher.nodes.values())[:2]
        original_states = [(n, n.healthy) for n in nodes]

        for node in nodes:
            node.healthy = False

        requests = [
            ToolCallRequest(
                tool_name=f"tool_{i % 10}",
                args={"index": i},
                request_id=f"req_{i}",
            )
            for i in range(100)
        ]

        successful = 0

        with BenchmarkTimer("multiple_node_failures") as timer:
            for req in requests:
                result = self.dispatcher.dispatch_call(req)
                if result.success:
                    successful += 1

        # Restore
        for node, was_healthy in original_states:
            node.healthy = was_healthy

        return {
            'failed_nodes': len(nodes),
            'total_requests': len(requests),
            'successful': successful,
            'success_rate_pct': (successful / len(requests)) * 100,
        }

    def _test_recovery(self) -> Dict[str, Any]:
        """Test recovery after transient failures."""
        node = list(self.dispatcher.nodes.values())[0]

        # Simulate transient failures
        node.failed_calls = 5
        node.total_calls = 10

        # Execute requests to observe recovery
        requests = [
            ToolCallRequest(
                tool_name=f"tool_{i}",
                args={"index": i},
                request_id=f"req_{i}",
            )
            for i in range(50)
        ]

        with BenchmarkTimer("recovery") as timer:
            for req in requests:
                result = self.dispatcher.dispatch_call(req)

        return {
            'recovery_time_ms': timer.elapsed_ms,
            'final_node_health': node.healthy,
        }

    # =========================================================================
    # BENCHMARK: End-to-End Scaling
    # =========================================================================

    def benchmark_end_to_end_scaling(self) -> Dict[str, Any]:
        """Measure end-to-end performance at scale.

        Simulates production load: 1M tool calls with realistic distribution.
        """
        self._log(f"Benchmarking end-to-end scaling ({self.num_calls} calls)...")

        # Generate realistic request distribution
        requests = []
        tool_distribution = [
            ('read_file', 0.25),
            ('terminal', 0.30),
            ('browser', 0.20),
            ('llm_call', 0.15),
            ('memory', 0.10),
        ]

        for i in range(self.num_calls):
            # Choose tool by distribution
            rand = random.random()
            cumul = 0
            tool = 'read_file'

            for tool_name, prob in tool_distribution:
                cumul += prob
                if rand < cumul:
                    tool = tool_name
                    break

            requests.append(ToolCallRequest(
                tool_name=tool,
                args={"request_id": i},
                request_id=f"req_{i}",
            ))

        # Dispatch all requests
        with BenchmarkTimer("end_to_end_scaling") as timer:
            results = self.dispatcher.dispatch_batch(requests)

        successful = sum(1 for r in results if r.success)

        throughput_cps = self.num_calls / (timer.elapsed_ms / 1000) if timer.elapsed_ms > 0 else 0

        # Calculate percentiles
        latencies = [r.latency_ms for r in results if r.latency_ms > 0]
        latencies.sort()

        return {
            'total_calls': self.num_calls,
            'successful_calls': successful,
            'success_rate_pct': (successful / self.num_calls) * 100,
            'total_time_seconds': timer.elapsed_ms / 1000,
            'throughput_calls_per_sec': throughput_cps,
            'avg_latency_ms': statistics.mean(latencies) if latencies else 0,
            'p50_latency_ms': latencies[int(len(latencies) * 0.50)] if latencies else 0,
            'p95_latency_ms': latencies[int(len(latencies) * 0.95)] if latencies else 0,
            'p99_latency_ms': latencies[int(len(latencies) * 0.99)] if latencies else 0,
        }

    # =========================================================================
    # REPORT GENERATION
    # =========================================================================

    def run_all_benchmarks(self) -> Dict[str, Any]:
        """Run complete benchmark suite."""
        self._log("Starting Phase 3 benchmark suite...", "RESULT")

        start_time = time.time()
        results = {
            'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
            'configuration': {
                'num_calls': self.num_calls,
                'num_nodes': len(self.dispatcher.nodes),
                'num_tools': 20,
            },
        }

        # Run benchmarks
        try:
            results['hash_ring_distribution'] = self.benchmark_hash_ring_distribution()
            results['load_balancing'] = self.benchmark_load_balancing()
            results['batching_efficiency'] = self.benchmark_batching_efficiency()
            results['schema_cache'] = self.benchmark_schema_cache()
            results['distributed_consensus'] = self.benchmark_distributed_consensus()
            results['fault_tolerance'] = self.benchmark_fault_tolerance()
            results['end_to_end_scaling'] = self.benchmark_end_to_end_scaling()
        except Exception as e:
            logger.error(f"Benchmark failed: {e}", exc_info=True)
            results['error'] = str(e)

        results['total_time_seconds'] = time.time() - start_time

        return results

    def print_report(self, results: Dict[str, Any]) -> None:
        """Print formatted benchmark report."""
        print("\n" + "="*80)
        print("PHASE 3 TOOL CALL ACCELERATION - BENCHMARK RESULTS")
        print("="*80 + "\n")

        print(f"Configuration: {results['configuration']}")
        print(f"Total time: {results['total_time_seconds']:.2f}s\n")

        # Hash ring distribution
        hr = results.get('hash_ring_distribution', {})
        print(f"Hash Ring Distribution:")
        print(f"  Lookup latency: {hr.get('lookup_latency_ms', 0):.4f}ms")
        print(f"  Distribution uniformity: {hr.get('distribution_uniformity_pct', 0):.2f}%")
        print(f"  Target: 5%\n")

        # Load balancing
        lb = results.get('load_balancing', {})
        print(f"Load Balancing:")
        print(f"  Routing latency: {lb.get('routing_latency_ms', 0):.4f}ms")
        print(f"  Load uniformity: {lb.get('load_uniformity_pct', 0):.2f}%\n")

        # Batching
        be = results.get('batching_efficiency', {})
        print(f"Batching Efficiency:")
        for batch_info in be.values():
            if isinstance(batch_info, dict) and 'throughput_calls_per_sec' in batch_info:
                print(f"  Throughput: {batch_info['throughput_calls_per_sec']:,.0f} calls/sec")
        print()

        # Schema cache
        sc = results.get('schema_cache', {})
        print(f"Schema Cache:")
        print(f"  Hit rate: {sc.get('hit_rate_pct', 0):.2f}%")
        print(f"  Access latency: {sc.get('access_latency_us', 0):.4f}us\n")

        # End-to-end scaling
        e2e = results.get('end_to_end_scaling', {})
        print(f"End-to-End Scaling ({e2e.get('total_calls', 0)} calls):")
        print(f"  Throughput: {e2e.get('throughput_calls_per_sec', 0):,.0f} calls/sec")
        print(f"  Success rate: {e2e.get('success_rate_pct', 0):.2f}%")
        print(f"  P99 latency: {e2e.get('p99_latency_ms', 0):.2f}ms\n")

        print("="*80)


def main():
    """Run benchmark suite."""
    import argparse

    parser = argparse.ArgumentParser(description="Phase 3 Tool Acceleration Benchmarks")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--profile", action="store_true", help="Enable profiling")
    parser.add_argument("--num-calls", type=int, default=10000, help="Number of test calls")

    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)

    bench = Phase3Benchmarks(verbose=args.verbose, num_calls=args.num_calls)
    results = bench.run_all_benchmarks()
    bench.print_report(results)

    # Save results to JSON
    output_file = Path(__file__).parent / "bench_phase3_results.json"
    with open(output_file, 'w', encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to {output_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
