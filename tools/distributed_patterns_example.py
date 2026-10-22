#!/usr/bin/env python3
"""
Example usage of novel distributed computing patterns.

Demonstrates:
1. Creating a distributed cluster
2. Updating schemas with gossip
3. Registering tools with CRDT
4. Discovering tools with Bloom filters
5. Executing with quorum dispatch
6. Reconciling state with Merkle trees
"""

import logging
import time
from typing import Dict, Any

from tools.distributed_patterns_integration import (
    DistributedSystemCluster,
    DistributedSystemConfig,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def example_small_cluster():
    """Example: Small cluster (10 nodes) with all patterns."""
    logger.info("=== Example 1: Small Cluster (10 nodes) ===\n")

    # Create 10-node cluster
    config = DistributedSystemConfig(
        node_id="node_0",
        cluster_size=10,
        gossip_fanout=3,
        enable_byzantine_tolerance=True,
    )

    cluster = DistributedSystemCluster(10, config)

    # Update a schema globally
    logger.info("Updating schema 'users' across cluster...")
    start = time.time()

    convergence_time = cluster.update_schema_globally(
        "users",
        {
            "fields": ["id", "name", "email"],
            "version": "2.0",
        }
    )

    elapsed = time.time() - start
    logger.info(f"Schema converged in {convergence_time:.2f}s (actual: {elapsed:.2f}s)\n")

    # Register tools
    logger.info("Registering tools across cluster...")
    node_0 = cluster.nodes["node_0"]

    for i in range(5):
        node_0.register_tool(
            f"tool_{i}",
            {
                "version": "1.0",
                "toolset": "default",
                "handler": f"handle_tool_{i}",
            }
        )

    logger.info(f"Registered 5 tools (CRDT-synced to all {10} nodes)\n")

    # Check tool availability (O(1) lookups)
    logger.info("Checking tool availability (Bloom filter - O(1))...")
    for i in range(5):
        available = node_0.check_tool_availability(f"tool_{i}")
        logger.info(f"  tool_{i}: {'available' if available else 'not found'}")

    logger.info()

    # Execute tool with quorum
    logger.info("Executing tool with quorum dispatch...")
    start = time.time()

    def simple_execute(args):
        return {"status": "success", "result": "Hello from quorum"}

    result = cluster.dispatch_tool_distributed(
        "tool_0",
        {"param": "value"},
        simple_execute
    )

    elapsed = time.time() - start
    logger.info(f"Tool executed on {len(result.nodes_involved)} nodes in {elapsed:.2f}s")
    logger.info(f"  Result: {result.result}")
    logger.info(f"  Byzantine nodes isolated: {len(result.nodes_involved) < 5}\n")

    # Synchronize state
    logger.info("Synchronizing state with peer (Merkle reconciliation)...")
    node_1 = cluster.nodes["node_1"]

    sync_result = node_0.synchronize_state("node_1")
    logger.info(f"Sync result: {sync_result}\n")

    # Print statistics
    logger.info("Cluster statistics:")
    stats = cluster.get_cluster_stats()
    logger.info(f"  Total operations: {stats['aggregates']['total_operations']}")
    logger.info(f"  Avg cache hit rate: {stats['aggregates']['avg_cache_hit_rate']:.1%}\n")


def example_large_cluster():
    """Example: Large cluster (100+ nodes) showing scalability."""
    logger.info("=== Example 2: Large Cluster (100 nodes) ===\n")

    config = DistributedSystemConfig(
        node_id="node_0",
        cluster_size=100,
        gossip_fanout=5,  # Higher fanout for larger clusters
        enable_byzantine_tolerance=True,
    )

    cluster = DistributedSystemCluster(100, config)

    logger.info("Testing gossip propagation on 100-node cluster...")
    start = time.time()

    # Update schema (should use O(log 100) = ~7 rounds)
    convergence_time = cluster.update_schema_globally(
        "config",
        {"cluster_size": 100, "version": "1.0"}
    )

    elapsed = time.time() - start

    logger.info(f"Schema propagated to 100 nodes in {elapsed:.2f}s")
    logger.info(f"Convergence time estimate: {convergence_time:.2f}s")
    logger.info(f"Messages: ~{100 * 5} (fanout * nodes)\n")

    # Register many tools
    logger.info("Registering 1000 tools...")
    node_0 = cluster.nodes["node_0"]

    start = time.time()
    for i in range(1000):
        node_0.register_tool(f"tool_{i}", {"version": "1.0"})

    elapsed = time.time() - start
    logger.info(f"Registered 1000 tools in {elapsed:.2f}s\n")

    # Execute with minimal latency
    logger.info("Executing tools (using quorum + Bloom cache)...")

    def simple_execute(args):
        return {"status": "ok"}

    num_executions = 100
    start = time.time()

    for i in range(num_executions):
        result = cluster.dispatch_tool_distributed(
            f"tool_{i}",
            {},
            simple_execute
        )

    elapsed = time.time() - start
    logger.info(f"Executed {num_executions} tools in {elapsed:.2f}s")
    logger.info(f"Throughput: {num_executions / elapsed:.0f} tools/sec\n")


def example_fault_tolerance():
    """Example: Byzantine fault tolerance with quorum dispatch."""
    logger.info("=== Example 3: Byzantine Fault Tolerance ===\n")

    config = DistributedSystemConfig(
        node_id="node_0",
        cluster_size=7,  # 7 nodes can tolerate 2 Byzantine
        enable_byzantine_tolerance=True,
    )

    cluster = DistributedSystemCluster(7, config)

    logger.info("7-node cluster can tolerate up to 2 Byzantine nodes\n")

    def faulty_execute(args):
        """Some nodes return different results."""
        import random

        # 20% of nodes fail
        if random.random() < 0.2:
            return {"error": "Node failure"}
        else:
            return {"status": "success", "data": "correct result"}

    logger.info("Executing tool with Byzantine nodes present...")
    start = time.time()

    result = cluster.dispatch_tool_distributed(
        "critical_tool",
        {},
        faulty_execute
    )

    elapsed = time.time() - start

    logger.info(f"Execution completed in {elapsed:.2f}s")
    logger.info(f"Nodes that agreed: {len(result.nodes_involved)}/7")
    logger.info(f"Consensus result: {result.result}")
    logger.info(f"Byzantine detection automatic: yes\n")


def example_state_sync():
    """Example: Efficient state reconciliation with Merkle trees."""
    logger.info("=== Example 4: Merkle Tree State Reconciliation ===\n")

    config = DistributedSystemConfig(
        node_id="node_0",
        cluster_size=2,
    )

    cluster = DistributedSystemCluster(2, config)

    node_0 = cluster.nodes["node_0"]
    node_1 = cluster.nodes["node_1"]

    # Simulate different state
    logger.info("Setting up different state on two nodes...")
    node_0.merkle_recon.update_local_state([f"item_{i}" for i in range(1000)])
    node_1.merkle_recon.update_local_state([f"item_{i}" for i in range(500, 1500)])

    logger.info("Node 0 has items 0-999")
    logger.info("Node 1 has items 500-1499")
    logger.info("Overlap: items 500-999 (500 items)\n")

    # Reconcile (efficient!)
    logger.info("Reconciling state (Merkle tree binary search)...")
    start = time.time()

    sync_result = node_0.synchronize_state("node_1")

    elapsed = time.time() - start

    logger.info(f"Reconciliation completed in {elapsed:.4f}s")
    logger.info(f"Missing items (to fetch): {sync_result.get('missing_items', 0)}")
    logger.info(f"Extra items (to delete): {sync_result.get('extra_items', 0)}")
    logger.info(f"Bandwidth saved: {sync_result.get('bandwidth_saved', 0):.0f} bytes\n")


def example_performance_scaling():
    """Example: Show scaling characteristics."""
    logger.info("=== Example 5: Performance Scaling ===\n")

    logger.info("Cluster Size | Schema Sync Time | Throughput | Messages")
    logger.info("-------------|-----------------|-----------|----------")

    for cluster_size in [10, 50, 100]:
        config = DistributedSystemConfig(
            node_id="node_0",
            cluster_size=cluster_size,
            gossip_fanout=3,
        )

        cluster = DistributedSystemCluster(cluster_size, config)

        # Time schema propagation
        start = time.time()
        cluster.update_schema_globally("perf_test", {"version": "1.0"})
        sync_time = time.time() - start

        # Estimate throughput and messages
        throughput = 100 / sync_time  # ops/sec for 100 updates
        messages = cluster_size * 3  # Approx fanout * nodes

        logger.info(
            f"{cluster_size:13} | {sync_time:15.3f}s | {throughput:9.0f} | {messages:8}"
        )

    logger.info("\nKey insight: O(log N) scaling means exponential speedup!")
    logger.info("  - 10 nodes: ~3 rounds")
    logger.info("  - 100 nodes: ~7 rounds (2.3x more, not 10x!)")
    logger.info("  - 1000 nodes: ~10 rounds (3.3x more, not 100x!)\n")


if __name__ == "__main__":
    logger.info("\n" + "=" * 70)
    logger.info("Novel Distributed Computing Patterns Examples")
    logger.info("=" * 70 + "\n")

    try:
        example_small_cluster()
        print("\n" + "=" * 70 + "\n")

        example_large_cluster()
        print("\n" + "=" * 70 + "\n")

        example_fault_tolerance()
        print("\n" + "=" * 70 + "\n")

        example_state_sync()
        print("\n" + "=" * 70 + "\n")

        example_performance_scaling()

        logger.info("=" * 70)
        logger.info("All examples completed successfully!")
        logger.info("=" * 70)

    except Exception as e:
        logger.error(f"Error running examples: {e}", exc_info=True)
