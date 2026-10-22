#!/usr/bin/env python3
"""
Distributed Tool Call Dispatcher — Phase 3 Acceleration

Distributes tool calls across multiple machines using consistent hashing and
load balancing to achieve 1B+ tool calls/sec globally. Handles:

  - Consistent hashing for deterministic tool-to-node mapping
  - Load balancing across dispatch nodes with dynamic reweighting
  - Fault tolerance with automatic failover
  - Batching requests to minimize RPC overhead
  - Network-efficient marshalling

Architecture:
  1. Client sends tool call to dispatcher
  2. Dispatcher uses consistent hash to find responsible node
  3. Node executes tool and returns result
  4. Failed nodes are removed from ring; succeeding nodes rebalanced
  5. Batched calls are sent as a single RPC to minimize overhead
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from collections import defaultdict
import heapq

logger = logging.getLogger(__name__)

# Configuration
_DEFAULT_VIRTUAL_NODES = 150  # Virtual nodes per physical node in hash ring
_DEFAULT_REPLICATION_FACTOR = 3  # How many nodes hold each tool's data
_DEFAULT_BATCH_TIMEOUT_MS = 10  # Max time to wait before sending a batch
_DEFAULT_BATCH_SIZE = 100  # Max calls per batch


@dataclass(frozen=True)
class ToolCallRequest:
    """Single tool call to be dispatched."""
    tool_name: str
    args: Dict[str, Any]
    request_id: str
    timeout_ms: float = 30000.0


@dataclass(frozen=True)
class ToolCallResult:
    """Result of a tool call execution."""
    request_id: str
    tool_name: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    latency_ms: float = 0.0
    node_id: Optional[str] = None


@dataclass
class DispatchNode:
    """Represents a dispatch node in the cluster."""
    node_id: str
    address: str
    port: int
    weight: float = 1.0
    healthy: bool = True
    load: int = 0
    last_heartbeat: float = field(default_factory=time.time)
    failed_calls: int = 0
    total_calls: int = 0

    def get_health_score(self) -> float:
        """Calculate health score: weight * (1 - error_rate) * reachability."""
        if self.total_calls == 0:
            return self.weight
        error_rate = self.failed_calls / max(1, self.total_calls)
        return self.weight * (1.0 - error_rate)


class ConsistentHashRing:
    """Consistent hashing ring for deterministic tool-to-node mapping.

    Uses SHA-256 hash of (tool_name, args_hash) to find responsible nodes.
    Virtual nodes reduce load imbalance and enable smooth rebalancing.
    """

    def __init__(self, virtual_nodes: int = _DEFAULT_VIRTUAL_NODES):
        self.virtual_nodes = virtual_nodes
        self.ring: Dict[int, DispatchNode] = {}  # hash -> node mapping
        self.sorted_keys: List[int] = []
        self.node_replicas: Dict[str, List[int]] = defaultdict(list)  # node_id -> [hashes]
        self._lock = threading.RLock()

    def _hash_key(self, key: str) -> int:
        """Consistent hash using SHA-256."""
        return int(hashlib.sha256(key.encode()).hexdigest(), 16)

    def add_node(self, node: DispatchNode) -> None:
        """Add a node and its virtual replicas to the ring."""
        with self._lock:
            for i in range(self.virtual_nodes):
                virtual_key = f"{node.node_id}:{i}"
                hash_val = self._hash_key(virtual_key)
                self.ring[hash_val] = node
                self.node_replicas[node.node_id].append(hash_val)

            self.sorted_keys = sorted(self.ring.keys())
            logger.info(f"Added node {node.node_id} with {self.virtual_nodes} virtual nodes")

    def remove_node(self, node_id: str) -> None:
        """Remove a node from the ring."""
        with self._lock:
            if node_id not in self.node_replicas:
                return

            for hash_val in self.node_replicas[node_id]:
                del self.ring[hash_val]

            del self.node_replicas[node_id]
            self.sorted_keys = sorted(self.ring.keys())
            logger.warning(f"Removed node {node_id} from hash ring")

    def get_nodes(self, tool_name: str, args_hash: str,
                 count: int = _DEFAULT_REPLICATION_FACTOR) -> List[DispatchNode]:
        """Get N replicas for a tool call using consistent hashing.

        Returns nodes in order of preference. All returns are healthy nodes
        only; if fewer than N healthy nodes exist, returns what's available.
        """
        with self._lock:
            if not self.sorted_keys:
                return []

            # Hash the tool call
            key = f"{tool_name}:{args_hash}"
            hash_val = self._hash_key(key)

            # Binary search to find starting point
            idx = self._find_start_index(hash_val)

            # Collect N unique healthy nodes
            nodes: List[DispatchNode] = []
            seen_ids: Set[str] = set()

            for i in range(len(self.sorted_keys)):
                ring_idx = (idx + i) % len(self.sorted_keys)
                node = self.ring[self.sorted_keys[ring_idx]]

                if node.node_id not in seen_ids and node.healthy:
                    nodes.append(node)
                    seen_ids.add(node.node_id)
                    if len(nodes) >= count:
                        break

            return nodes

    def _find_start_index(self, hash_val: int) -> int:
        """Binary search to find first key >= hash_val."""
        keys = self.sorted_keys
        left, right = 0, len(keys)

        while left < right:
            mid = (left + right) // 2
            if keys[mid] < hash_val:
                left = mid + 1
            else:
                right = mid

        return left % len(keys) if keys else 0


class DispatchBatcher:
    """Batches tool calls to minimize RPC overhead.

    Accumulates requests until timeout or batch size limit, then sends
    as a single RPC. Responses are demultiplexed back to callers.
    """

    def __init__(self, node: DispatchNode, batch_size: int = _DEFAULT_BATCH_SIZE,
                 batch_timeout_ms: float = _DEFAULT_BATCH_TIMEOUT_MS):
        self.node = node
        self.batch_size = batch_size
        self.batch_timeout_ms = batch_timeout_ms

        self.batch: List[ToolCallRequest] = []
        self.batch_lock = threading.Lock()
        self.batch_event = threading.Event()
        self.pending_futures: Dict[str, Any] = {}

    def add_request(self, request: ToolCallRequest) -> None:
        """Queue a request for batching."""
        with self.batch_lock:
            self.batch.append(request)
            if len(self.batch) >= self.batch_size:
                self.batch_event.set()

    def get_batch(self) -> List[ToolCallRequest]:
        """Get accumulated batch, waiting up to timeout."""
        # Wait for either batch to fill or timeout
        self.batch_event.wait(timeout=self.batch_timeout_ms / 1000.0)

        with self.batch_lock:
            batch = self.batch[:]
            self.batch.clear()
            self.batch_event.clear()

        return batch


class DistributedDispatcher:
    """Central dispatcher managing tool calls across cluster.

    Owns the hash ring, node health tracking, load balancing, and RPC routing.
    Single point of coordination but not execution — actual tool runs on
    remote nodes.
    """

    def __init__(self, virtual_nodes: int = _DEFAULT_VIRTUAL_NODES,
                 replication_factor: int = _DEFAULT_REPLICATION_FACTOR):
        self.hash_ring = ConsistentHashRing(virtual_nodes)
        self.replication_factor = replication_factor

        self.nodes: Dict[str, DispatchNode] = {}
        self.batchers: Dict[str, DispatchBatcher] = {}

        self._lock = threading.RLock()
        self._stats = {
            'total_calls': 0,
            'successful_calls': 0,
            'failed_calls': 0,
            'batched_calls': 0,
            'total_batches': 0,
        }

        # Health check thread
        self._health_check_thread = None
        self._stop_health_checks = False

    def add_node(self, node_id: str, address: str, port: int,
                weight: float = 1.0) -> None:
        """Register a dispatch node in the cluster."""
        node = DispatchNode(
            node_id=node_id,
            address=address,
            port=port,
            weight=weight
        )

        with self._lock:
            self.nodes[node_id] = node
            self.hash_ring.add_node(node)
            self.batchers[node_id] = DispatchBatcher(node)
            logger.info(f"Added dispatch node: {node_id} ({address}:{port})")

    def dispatch_call(self, request: ToolCallRequest) -> ToolCallResult:
        """Dispatch a single tool call to appropriate node(s).

        Uses consistent hashing to find responsible nodes, sends request
        with automatic failover if primary fails.
        """
        start_time = time.time()

        # Compute args hash for consistent routing
        args_json = json.dumps(request.args, sort_keys=True, default=str)
        args_hash = hashlib.sha256(args_json.encode()).hexdigest()

        # Get replica nodes
        with self._lock:
            target_nodes = self.hash_ring.get_nodes(
                request.tool_name, args_hash, self.replication_factor
            )

        if not target_nodes:
            return ToolCallResult(
                request_id=request.request_id,
                tool_name=request.tool_name,
                success=False,
                error="No healthy dispatch nodes available"
            )

        # Try primary node first, then replicas on failure
        for node in target_nodes:
            try:
                result = self._execute_on_node(node, request)

                # Update stats
                with self._lock:
                    self._stats['total_calls'] += 1
                    node.total_calls += 1
                    if result.success:
                        self._stats['successful_calls'] += 1
                    else:
                        self._stats['failed_calls'] += 1
                        node.failed_calls += 1

                return result
            except Exception as e:
                logger.warning(f"Node {node.node_id} failed: {e}; trying next replica")
                with self._lock:
                    # Mark node as unhealthy after repeated failures
                    node.failed_calls += 1
                    if node.total_calls > 0:
                        error_rate = node.failed_calls / node.total_calls
                        if error_rate > 0.5:  # >50% error rate
                            node.healthy = False
                            self.hash_ring.remove_node(node.node_id)
                continue

        # All replicas failed
        return ToolCallResult(
            request_id=request.request_id,
            tool_name=request.tool_name,
            success=False,
            error=f"All {len(target_nodes)} replicas failed"
        )

    def dispatch_batch(self, requests: List[ToolCallRequest]) -> List[ToolCallResult]:
        """Dispatch multiple tool calls with request batching.

        Groups calls by destination node and sends each group as a single RPC.
        """
        results: Dict[str, ToolCallResult] = {}

        # Group requests by destination node
        requests_by_node: Dict[str, List[ToolCallRequest]] = defaultdict(list)

        for request in requests:
            args_json = json.dumps(request.args, sort_keys=True, default=str)
            args_hash = hashlib.sha256(args_json.encode()).hexdigest()

            with self._lock:
                target_nodes = self.hash_ring.get_nodes(
                    request.tool_name, args_hash, 1
                )

            if target_nodes:
                node_id = target_nodes[0].node_id
                requests_by_node[node_id].append(request)

        # Send each batch to its node
        with self._lock:
            self._stats['total_batches'] += 1
            self._stats['batched_calls'] += len(requests)

        for node_id, batch_requests in requests_by_node.items():
            with self._lock:
                node = self.nodes.get(node_id)

            if node:
                try:
                    batch_results = self._execute_batch_on_node(node, batch_requests)
                    results.update({r.request_id: r for r in batch_results})
                except Exception as e:
                    logger.error(f"Batch execution on {node_id} failed: {e}")
                    for req in batch_requests:
                        results[req.request_id] = ToolCallResult(
                            request_id=req.request_id,
                            tool_name=req.tool_name,
                            success=False,
                            error=str(e)
                        )

        # Return results in original order
        return [results.get(r.request_id) for r in requests]

    def _execute_on_node(self, node: DispatchNode,
                        request: ToolCallRequest) -> ToolCallResult:
        """Execute a single tool call on a specific node (RPC stub)."""
        # In real implementation, this would make an RPC call
        # For now, simulate execution timing
        start = time.time()

        # Simulate tool execution (would be actual RPC)
        try:
            # In production: call node.address:node.port with request
            # Return ToolCallResult with actual result

            # Simulated execution
            time.sleep(0.001)  # 1ms latency

            latency_ms = (time.time() - start) * 1000
            return ToolCallResult(
                request_id=request.request_id,
                tool_name=request.tool_name,
                success=True,
                result={"status": "ok"},
                latency_ms=latency_ms,
                node_id=node.node_id
            )
        except Exception as e:
            return ToolCallResult(
                request_id=request.request_id,
                tool_name=request.tool_name,
                success=False,
                error=str(e),
                node_id=node.node_id
            )

    def _execute_batch_on_node(self, node: DispatchNode,
                              requests: List[ToolCallRequest]) -> List[ToolCallResult]:
        """Execute multiple tool calls as a single batch on a node."""
        start = time.time()
        results = []

        try:
            # Simulate batch RPC
            # In production: serialize requests, send to node, deserialize results
            time.sleep(0.0005 * len(requests))  # Variable latency

            for request in requests:
                results.append(ToolCallResult(
                    request_id=request.request_id,
                    tool_name=request.tool_name,
                    success=True,
                    result={"status": "ok"},
                    latency_ms=(time.time() - start) * 1000,
                    node_id=node.node_id
                ))
        except Exception as e:
            for request in requests:
                results.append(ToolCallResult(
                    request_id=request.request_id,
                    tool_name=request.tool_name,
                    success=False,
                    error=str(e),
                    node_id=node.node_id
                ))

        return results

    def start_health_checks(self, interval_seconds: float = 5.0) -> None:
        """Start background health check thread."""
        if self._health_check_thread:
            return

        def health_check_loop():
            while not self._stop_health_checks:
                with self._lock:
                    for node in self.nodes.values():
                        # Simulate health check heartbeat
                        node.last_heartbeat = time.time()
                        node.load = max(0, node.load - 1)  # Decay load

                time.sleep(interval_seconds)

        self._health_check_thread = threading.Thread(
            target=health_check_loop, daemon=True
        )
        self._health_check_thread.start()
        logger.info(f"Started health check thread (interval={interval_seconds}s)")

    def stop_health_checks(self) -> None:
        """Stop background health check thread."""
        self._stop_health_checks = True
        if self._health_check_thread:
            self._health_check_thread.join(timeout=5)

    def get_stats(self) -> Dict[str, Any]:
        """Get dispatcher statistics."""
        with self._lock:
            return {
                **self._stats,
                'nodes': {
                    node_id: {
                        'healthy': node.healthy,
                        'load': node.load,
                        'total_calls': node.total_calls,
                        'failed_calls': node.failed_calls,
                        'error_rate': (
                            node.failed_calls / max(1, node.total_calls)
                        ),
                    }
                    for node_id, node in self.nodes.items()
                }
            }

    def get_ring_stats(self) -> Dict[str, Any]:
        """Get hash ring statistics."""
        with self._lock:
            return {
                'num_nodes': len(self.nodes),
                'num_virtual_nodes': len(self.hash_ring.ring),
                'healthy_nodes': sum(1 for n in self.nodes.values() if n.healthy),
            }
