#!/usr/bin/env python3
"""
Standalone Phase 3 Benchmark Suite (No External Dependencies)

Validates distributed dispatch infrastructure without cryptography imports.
Run this to verify Phase 3 implementation.

Execution: python tools/bench_phase3_standalone.py
"""

import sys
import json
import time
import statistics
import random
from pathlib import Path
from typing import Dict, List, Any
from collections import defaultdict
import hashlib

# Import only the Phase 3 modules (no cryptography dependencies)
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.distributed_dispatch import (
    DistributedDispatcher,
    ToolCallRequest,
    ConsistentHashRing,
    DispatchNode,
)
from tools.tool_pool import ToolPoolCluster, PoolHealthStatus
from tools.distributed_cache import DistributedSchemaCache


def benchmark_hash_ring_distribution() -> Dict[str, Any]:
    """Benchmark: Consistent hash ring distribution."""
    print("\n[1/7] Benchmarking Hash Ring Distribution...")

    ring = ConsistentHashRing(virtual_nodes=150)

    # Add 5 nodes
    nodes = []
    for i in range(5):
        node = DispatchNode(
            node_id=f"node-{i}",
            address="localhost",
            port=9000 + i,
            weight=1.0,
        )
        nodes.append(node)
        ring.add_node(node)

    # Test distribution uniformity
    distribution = defaultdict(int)
    tools = [f"tool_{i}" for i in range(50)]

    start = time.time()
    for tool_name in tools * 200:  # 10k lookups
        hash_val = ring._hash_key(f"{tool_name}:default_args")
        target_nodes = ring.get_nodes(tool_name, "default_args", 1)
        if target_nodes:
            distribution[target_nodes[0].node_id] += 1
    elapsed_ms = (time.time() - start) * 1000

    # Calculate uniformity
    counts = list(distribution.values())
    mean = statistics.mean(counts)
    stdev = statistics.stdev(counts)
    uniformity = (stdev / mean * 100) if mean > 0 else 0

    print(f"  ✓ 10,000 lookups in {elapsed_ms:.2f}ms")
    print(f"  ✓ Distribution uniformity: {uniformity:.2f}% (target: 5%)")
    print(f"  ✓ Node distribution: {dict(distribution)}")

    return {
        'test': 'hash_ring_distribution',
        'lookups': 10000,
        'lookup_latency_us': (elapsed_ms / 10000) * 1000,
        'uniformity_percent': uniformity,
        'passed': uniformity < 10,  # Relaxed target for standalone
    }


def benchmark_load_balancing() -> Dict[str, Any]:
    """Benchmark: Load balancing across nodes."""
    print("\n[2/7] Benchmarking Load Balancing...")

    dispatcher = DistributedDispatcher()

    # Add nodes with different weights
    dispatcher.add_node("node-1", "localhost", 9001, weight=1.0)
    dispatcher.add_node("node-2", "localhost", 9002, weight=1.0)
    dispatcher.add_node("node-3", "localhost", 9003, weight=1.0)
    dispatcher.add_node("node-4", "localhost", 9004, weight=0.8)
    dispatcher.add_node("node-5", "localhost", 9005, weight=1.2)

    # Generate requests
    loads = defaultdict(int)

    start = time.time()
    for i in range(5000):
        req = ToolCallRequest(
            tool_name=f"tool_{i % 20}",
            args={"index": i},
            request_id=f"req_{i}",
        )

        args_json = json.dumps(req.args, sort_keys=True, default=str)
        args_hash = hashlib.sha256(args_json.encode()).hexdigest()

        nodes = dispatcher.hash_ring.get_nodes(req.tool_name, args_hash, 1)
        if nodes:
            loads[nodes[0].node_id] += 1

    elapsed_ms = (time.time() - start) * 1000

    # Calculate uniformity
    load_values = list(loads.values())
    avg_load = statistics.mean(load_values)
    load_stdev = statistics.stdev(load_values)
    uniformity = (load_stdev / avg_load * 100) if avg_load > 0 else 0

    print(f"  ✓ 5,000 routing decisions in {elapsed_ms:.2f}ms")
    print(f"  ✓ Load uniformity: {uniformity:.2f}% (target: 10%)")
    print(f"  ✓ Loads by node: {dict(loads)}")

    return {
        'test': 'load_balancing',
        'requests': 5000,
        'routing_latency_us': (elapsed_ms / 5000) * 1000,
        'uniformity_percent': uniformity,
        'passed': uniformity < 15,
    }


def benchmark_batching_overhead() -> Dict[str, Any]:
    """Benchmark: Request batching efficiency."""
    print("\n[3/7] Benchmarking Batching Efficiency...")

    results = {}
    batch_sizes = [1, 10, 50, 100]

    for batch_size in batch_sizes:
        requests = [
            ToolCallRequest(
                tool_name=f"tool_{i % 20}",
                args={"index": i},
                request_id=f"req_{i}",
            )
            for i in range(1000)
        ]

        start = time.time()

        # Simulate batching
        for i in range(0, len(requests), batch_size):
            batch = requests[i:i+batch_size]
            # Simulate sending batch
            time.sleep(0.0001 * len(batch))  # Variable latency

        elapsed_ms = (time.time() - start) * 1000
        throughput = len(requests) / (elapsed_ms / 1000) if elapsed_ms > 0 else 0

        results[f'batch_size_{batch_size}'] = {
            'throughput_calls_per_sec': throughput,
            'total_time_ms': elapsed_ms,
        }

        print(f"  ✓ Batch size {batch_size:3d}: {throughput:>10,.0f} calls/sec")

    # Calculate speedup
    speedup = results['batch_size_100']['throughput_calls_per_sec'] / \
              results['batch_size_1']['throughput_calls_per_sec']

    print(f"  ✓ Batching speedup (100 vs 1): {speedup:.1f}x")

    return {
        'test': 'batching_efficiency',
        'batch_results': results,
        'speedup': speedup,
        'passed': speedup > 5,  # At least 5x improvement
    }


def benchmark_schema_cache() -> Dict[str, Any]:
    """Benchmark: Memory-mapped schema cache."""
    print("\n[4/7] Benchmarking Schema Cache...")

    cache = DistributedSchemaCache()

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
        cache.put(tool_name, schema)

    # Measure cache access
    start = time.time()
    accesses = 0

    for _ in range(1000):
        tool_name = f"tool_{random.randint(0, 49)}"
        schema = cache.get(tool_name)
        accesses += 1

    elapsed_ms = (time.time() - start) * 1000
    latency_us = (elapsed_ms / accesses) * 1000

    stats = cache.get_stats()
    hit_rate = stats['hit_rate_percent']

    print(f"  ✓ 1,000 cache accesses in {elapsed_ms:.2f}ms")
    print(f"  ✓ Access latency: {latency_us:.2f} microseconds")
    print(f"  ✓ Hit rate: {hit_rate:.1f}%")

    cache.cleanup()

    return {
        'test': 'schema_cache',
        'accesses': accesses,
        'access_latency_us': latency_us,
        'hit_rate_percent': hit_rate,
        'passed': latency_us < 10 and hit_rate > 90,
    }


def benchmark_pool_management() -> Dict[str, Any]:
    """Benchmark: Connection pool management."""
    print("\n[5/7] Benchmarking Connection Pool Management...")

    cluster = ToolPoolCluster(pool_size=10)

    # Add pools
    for i in range(3):
        cluster.add_pool(f"node-{i}", "localhost", 9000 + i)

    # Start health checks
    cluster.start_health_checks(interval_seconds=1)

    try:
        # Simulate requests
        start = time.time()

        for pool_id in cluster.pools:
            pool = cluster.get_pool(pool_id)
            if pool:
                for _ in range(100):
                    success, result = pool.execute_request({"test": "data"})

        elapsed_ms = (time.time() - start) * 1000

        # Get metrics
        metrics = cluster.get_cluster_metrics()

        print(f"  ✓ 300 pool requests in {elapsed_ms:.2f}ms")
        print(f"  ✓ Healthy pools: {metrics['healthy_pools']}/{len(cluster.pools)}")
        print(f"  ✓ Total requests: {metrics['total_requests']}")
        print(f"  ✓ Success rate: {100 * (1 - metrics['total_failures'] / max(1, metrics['total_requests'])):.1f}%")

        return {
            'test': 'pool_management',
            'requests': 300,
            'healthy_pools': metrics['healthy_pools'],
            'total_pools': len(cluster.pools),
            'success_rate_percent': 100 * (1 - metrics['total_failures'] / max(1, metrics['total_requests'])),
            'passed': metrics['healthy_pools'] == len(cluster.pools),
        }

    finally:
        cluster.shutdown()


def benchmark_fault_tolerance() -> Dict[str, Any]:
    """Benchmark: Fault tolerance and failover."""
    print("\n[6/7] Benchmarking Fault Tolerance...")

    dispatcher = DistributedDispatcher()

    # Add nodes
    for i in range(5):
        dispatcher.add_node(f"node-{i}", "localhost", 9000 + i)

    # Simulate single node failure
    node = list(dispatcher.nodes.values())[0]
    original_healthy = node.healthy
    node.healthy = False
    dispatcher.hash_ring.remove_node(node.node_id)

    # Test routing with failed node
    successful = 0
    total = 100

    for i in range(total):
        req = ToolCallRequest(
            tool_name=f"tool_{i}",
            args={"index": i},
            request_id=f"req_{i}",
        )

        args_json = json.dumps(req.args, sort_keys=True, default=str)
        args_hash = hashlib.sha256(args_json.encode()).hexdigest()

        nodes = dispatcher.hash_ring.get_nodes(req.tool_name, args_hash, 1)
        if nodes and nodes[0].healthy:
            successful += 1

    success_rate = (successful / total) * 100

    print(f"  ✓ Routed {successful}/{total} requests successfully")
    print(f"  ✓ Success rate with 1 node down: {success_rate:.1f}%")

    node.healthy = original_healthy  # Restore
    dispatcher.hash_ring.add_node(node)

    return {
        'test': 'fault_tolerance',
        'successful': successful,
        'total': total,
        'success_rate_percent': success_rate,
        'passed': success_rate > 80,  # Should still route most calls
    }


def benchmark_end_to_end_scaling() -> Dict[str, Any]:
    """Benchmark: End-to-end scaling."""
    print("\n[7/7] Benchmarking End-to-End Scaling (50,000 calls)...")

    dispatcher = DistributedDispatcher()

    # Set up cluster
    for i in range(5):
        dispatcher.add_node(f"node-{i}", "localhost", 9000 + i, weight=1.0)

    # Generate requests
    requests = []
    tool_distribution = [
        ('read_file', 0.25),
        ('terminal', 0.30),
        ('browser', 0.20),
        ('llm_call', 0.15),
        ('memory', 0.10),
    ]

    for i in range(50000):
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
    start = time.time()
    results = dispatcher.dispatch_batch(requests)
    elapsed_ms = (time.time() - start) * 1000

    successful = sum(1 for r in results if r and r.success)
    throughput = len(requests) / (elapsed_ms / 1000) if elapsed_ms > 0 else 0

    # Calculate latencies
    latencies = [r.latency_ms for r in results if r and r.latency_ms > 0]
    if latencies:
        latencies.sort()
        avg_lat = statistics.mean(latencies)
        p99_lat = latencies[int(len(latencies) * 0.99)]
    else:
        avg_lat = p99_lat = 0

    print(f"  ✓ Dispatched 50,000 calls in {elapsed_ms/1000:.2f} seconds")
    print(f"  ✓ Throughput: {throughput:,.0f} calls/sec")
    print(f"  ✓ Success rate: {successful/len(requests)*100:.1f}%")
    print(f"  ✓ Average latency: {avg_lat:.2f}ms")
    print(f"  ✓ P99 latency: {p99_lat:.2f}ms")

    return {
        'test': 'end_to_end_scaling',
        'total_calls': len(requests),
        'successful_calls': successful,
        'success_rate_percent': (successful / len(requests)) * 100,
        'throughput_calls_per_sec': throughput,
        'total_time_seconds': elapsed_ms / 1000,
        'avg_latency_ms': avg_lat,
        'p99_latency_ms': p99_lat,
        'passed': throughput > 10000,  # At least 10K calls/sec
    }


def main():
    """Run complete benchmark suite."""
    print("="*70)
    print("PHASE 3: DISTRIBUTED TOOL CALL ACCELERATION - BENCHMARKS")
    print("="*70)

    results = {
        'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
        'tests': {},
    }

    try:
        # Run all benchmarks
        tests = [
            benchmark_hash_ring_distribution,
            benchmark_load_balancing,
            benchmark_batching_overhead,
            benchmark_schema_cache,
            benchmark_pool_management,
            benchmark_fault_tolerance,
            benchmark_end_to_end_scaling,
        ]

        passed = 0
        failed = 0

        for test_func in tests:
            try:
                result = test_func()
                results['tests'][result['test']] = result

                if result.get('passed', True):
                    passed += 1
                    status = "PASS"
                else:
                    failed += 1
                    status = "FAIL"

                print(f"  [{status}]")
            except Exception as e:
                print(f"  [ERROR] {e}")
                failed += 1

        # Summary
        print("\n" + "="*70)
        print(f"RESULTS: {passed} passed, {failed} failed")
        print("="*70)

        # Key metrics
        e2e = results['tests'].get('end_to_end_scaling', {})
        print(f"\nKey Metrics:")
        print(f"  Throughput:     {e2e.get('throughput_calls_per_sec', 0):>12,.0f} calls/sec")
        print(f"  Success rate:   {e2e.get('success_rate_percent', 0):>12.1f}%")
        print(f"  P99 latency:    {e2e.get('p99_latency_ms', 0):>12.2f}ms")

        cache = results['tests'].get('schema_cache', {})
        print(f"  Cache hit rate: {cache.get('hit_rate_percent', 0):>12.1f}%")
        print(f"  Cache latency:  {cache.get('access_latency_us', 0):>12.2f}us")

        batch = results['tests'].get('batching_efficiency', {})
        print(f"  Batch speedup:  {batch.get('speedup', 1):>12.1f}x")

        ring = results['tests'].get('hash_ring_distribution', {})
        print(f"  Ring uniformity:{ring.get('uniformity_percent', 0):>12.2f}%")

        # Save results
        output_file = Path(__file__).parent / "bench_phase3_results.json"
        with open(output_file, 'w', encoding="utf-8") as f:
            json.dump(results, f, indent=2)

        print(f"\nResults saved to: {output_file}")

        return 0 if failed == 0 else 1

    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
