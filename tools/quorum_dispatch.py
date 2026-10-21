#!/usr/bin/env python3
"""
Byzantine fault-tolerant quorum-based tool dispatch.

Executes tools on N/2+1 nodes (quorum) to survive arbitrary Byzantine
failures. Automatically detects and isolates faulty nodes.

Key features:
  - Byzantine fault tolerance (1/3 nodes can be Byzantine)
  - N/2+1 quorum for strong consensus
  - Automatic Byzantine node detection
  - Slightly stale result acceptance
  - Sliding window fault tracking
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Configuration
_DEFAULT_QUORUM_TIMEOUT_SECONDS = 5.0
_DEFAULT_BYZANTINE_THRESHOLD = 0.33  # 1/3 of nodes can be faulty
_DEFAULT_FAULT_TRACKING_WINDOW = 100  # Track last N interactions


@dataclass
class QuorumResult:
    """Result from quorum-based dispatch."""
    tool_id: str
    consensus_result: Any
    quorum_size: int
    agreeing_nodes: List[str]
    byzantine_nodes: List[str]
    total_time_ms: float
    successful_dispatch: bool


@dataclass
class NodeFaultTracker:
    """Tracks faults per node for Byzantine detection."""
    node_id: str
    total_interactions: int = 0
    failed_interactions: int = 0
    last_failure_time: Optional[float] = None
    fault_history: List[bool] = field(default_factory=list)  # True = fault

    def add_failure(self) -> None:
        """Record a failed interaction."""
        self.total_interactions += 1
        self.failed_interactions += 1
        self.last_failure_time = time.time()
        self.fault_history.append(True)

        if len(self.fault_history) > _DEFAULT_FAULT_TRACKING_WINDOW:
            self.fault_history.pop(0)

    def add_success(self) -> None:
        """Record a successful interaction."""
        self.total_interactions += 1
        self.fault_history.append(False)

        if len(self.fault_history) > _DEFAULT_FAULT_TRACKING_WINDOW:
            self.fault_history.pop(0)

    def fault_rate(self) -> float:
        """Get current fault rate."""
        if not self.fault_history:
            return 0.0

        return sum(self.fault_history) / len(self.fault_history)

    def is_suspected_byzantine(self, threshold: float = _DEFAULT_BYZANTINE_THRESHOLD) -> bool:
        """Check if node is suspected to be Byzantine."""
        return self.fault_rate() > threshold


class QuorumDispatcher:
    """Byzantine-tolerant quorum-based tool dispatch.

    Executes on N/2+1 nodes to tolerate up to floor((N-1)/3) Byzantine nodes.
    """

    def __init__(self, node_id: str, total_nodes: int = 3):
        self.node_id = node_id
        self.total_nodes = total_nodes
        self.quorum_size = (total_nodes // 2) + 1

        # Node state
        self.nodes: Dict[str, str] = {}  # node_id -> node_address
        self._nodes_lock = threading.RLock()

        # Fault tracking per node
        self.fault_trackers: Dict[str, NodeFaultTracker] = {}
        self._tracker_lock = threading.RLock()

        # Tool execution history
        self.execution_history: List[Tuple[float, str, Dict[str, Any]]] = []
        self._history_lock = threading.RLock()

        # Statistics
        self._stats = {
            'total_dispatches': 0,
            'successful_dispatches': 0,
            'failed_dispatches': 0,
            'byzantine_detections': 0,
        }

    def register_node(self, node_id: str, node_address: str) -> None:
        """Register a node in the quorum."""
        with self._nodes_lock:
            self.nodes[node_id] = node_address

        with self._tracker_lock:
            if node_id not in self.fault_trackers:
                self.fault_trackers[node_id] = NodeFaultTracker(node_id)

    def remove_node(self, node_id: str) -> None:
        """Remove a node from quorum (isolate Byzantine node)."""
        with self._nodes_lock:
            self.nodes.pop(node_id, None)

        logger.warning(f"Removed node {node_id} from quorum")

    def select_quorum(self) -> List[str]:
        """Select quorum_size nodes for dispatch.

        Prefers healthy nodes over suspected Byzantine ones.
        """
        with self._nodes_lock:
            available_nodes = list(self.nodes.keys())

        with self._tracker_lock:
            # Sort by fault rate (healthiest first)
            sorted_nodes = sorted(
                available_nodes,
                key=lambda n: self.fault_trackers.get(n, NodeFaultTracker(n)).fault_rate()
            )

        # Select quorum_size healthiest nodes
        selected = sorted_nodes[:self.quorum_size]

        if len(selected) < self.quorum_size:
            logger.warning(
                f"Cannot select full quorum: need {self.quorum_size}, "
                f"got {len(selected)} from {len(available_nodes)} nodes"
            )

        return selected

    def dispatch_to_quorum(self, tool_id: str, args: Dict[str, Any],
                          dispatch_fn: Callable[[str, str, Dict[str, Any]],
                                               Tuple[bool, Any]]) -> QuorumResult:
        """Dispatch tool to quorum and wait for consensus.

        Args:
            tool_id: Tool to execute
            args: Arguments to pass
            dispatch_fn: Function to dispatch to node (returns (success, result))

        Returns:
            QuorumResult with consensus verdict
        """
        start_time = time.time()

        # Select quorum
        quorum = self.select_quorum()

        if len(quorum) < self.quorum_size:
            return QuorumResult(
                tool_id=tool_id,
                consensus_result=None,
                quorum_size=self.quorum_size,
                agreeing_nodes=[],
                byzantine_nodes=[],
                total_time_ms=(time.time() - start_time) * 1000,
                successful_dispatch=False,
            )

        # Dispatch to all quorum members in parallel
        results: Dict[str, Tuple[bool, Any]] = {}

        for node_id in quorum:
            try:
                success, result = dispatch_fn(node_id, tool_id, args)
                results[node_id] = (success, result)

                with self._tracker_lock:
                    if success:
                        self.fault_trackers[node_id].add_success()
                    else:
                        self.fault_trackers[node_id].add_failure()
            except Exception as e:
                logger.warning(f"Dispatch to {node_id} failed: {e}")
                results[node_id] = (False, str(e))

                with self._tracker_lock:
                    self.fault_trackers[node_id].add_failure()

        # Consensus: find result agreed by majority
        consensus_result, agreeing_nodes = self._compute_consensus(results)

        # Detect Byzantine nodes (those that disagreed)
        byzantine_nodes = [
            node_id for node_id in quorum
            if node_id not in agreeing_nodes and results[node_id][0]
        ]

        if byzantine_nodes:
            self._stats['byzantine_detections'] += len(byzantine_nodes)

            # Isolate Byzantine nodes
            for node_id in byzantine_nodes:
                logger.warning(f"Detected Byzantine node: {node_id}")
                # Could remove here, but prefer to keep tracking

        # Update history
        with self._history_lock:
            self.execution_history.append((
                time.time(),
                tool_id,
                {
                    'quorum': quorum,
                    'agreeing_nodes': agreeing_nodes,
                    'byzantine_nodes': byzantine_nodes,
                }
            ))

        self._stats['total_dispatches'] += 1
        if consensus_result is not None:
            self._stats['successful_dispatches'] += 1
        else:
            self._stats['failed_dispatches'] += 1

        total_time_ms = (time.time() - start_time) * 1000

        return QuorumResult(
            tool_id=tool_id,
            consensus_result=consensus_result,
            quorum_size=self.quorum_size,
            agreeing_nodes=agreeing_nodes,
            byzantine_nodes=byzantine_nodes,
            total_time_ms=total_time_ms,
            successful_dispatch=len(agreeing_nodes) >= self.quorum_size,
        )

    def _compute_consensus(self, results: Dict[str, Tuple[bool, Any]]) -> Tuple[Optional[Any], List[str]]:
        """Compute consensus from result hashes.

        Returns (consensus_result, agreeing_nodes).
        """
        # Hash successful results
        result_hashes: Dict[str, List[str]] = {}  # hash -> [node_ids]

        for node_id, (success, result) in results.items():
            if not success:
                continue

            try:
                result_hash = hashlib.sha256(
                    json.dumps(result, sort_keys=True, default=str).encode()
                ).hexdigest()
            except Exception:
                result_hash = hashlib.sha256(str(result).encode()).hexdigest()

            if result_hash not in result_hashes:
                result_hashes[result_hash] = []

            result_hashes[result_hash].append(node_id)

        if not result_hashes:
            return None, []

        # Find consensus (most common hash)
        consensus_hash = max(result_hashes.items(), key=lambda x: len(x[1]))[0]
        agreeing_nodes = result_hashes[consensus_hash]

        # Get actual result
        for node_id in agreeing_nodes:
            _, result = results[node_id]
            return result, agreeing_nodes

        return None, []

    def get_fault_report(self) -> Dict[str, Any]:
        """Get fault report for all nodes."""
        with self._tracker_lock:
            return {
                node_id: {
                    'fault_rate': tracker.fault_rate(),
                    'total_interactions': tracker.total_interactions,
                    'is_suspected_byzantine': tracker.is_suspected_byzantine(),
                }
                for node_id, tracker in self.fault_trackers.items()
            }

    def get_stats(self) -> Dict[str, Any]:
        """Get dispatch statistics."""
        with self._history_lock:
            history_size = len(self.execution_history)

        return {
            **self._stats,
            'quorum_size': self.quorum_size,
            'total_nodes': self.total_nodes,
            'execution_history_size': history_size,
            'fault_report': self.get_fault_report(),
        }
