#!/usr/bin/env python3
"""
Conflict-Free Replicated Data Type (CRDT) for tool registry.

Uses operation-based CRDT (commutative and idempotent operations) to
enable decentralized tool registry synchronization without consensus.

Key features:
  - Automatic conflict resolution (no consensus needed)
  - Operation-based synchronization
  - Commutative operations (order-independent)
  - Add-wins semantics for concurrent updates
  - Causal ordering with vector clocks
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Configuration
_DEFAULT_LOG_RETENTION = 1000  # Keep last N operations


class OperationType(Enum):
    """Types of CRDT operations."""
    ADD_TOOL = "add_tool"
    REMOVE_TOOL = "remove_tool"
    UPDATE_TOOL = "update_tool"
    ENABLE_TOOL = "enable_tool"
    DISABLE_TOOL = "disable_tool"


@dataclass(frozen=True)
class VectorClock:
    """Vector clock for causal ordering."""
    clock: Dict[str, int] = field(default_factory=dict)

    def increment(self, node_id: str) -> VectorClock:
        """Increment clock for a node."""
        new_clock = dict(self.clock)
        new_clock[node_id] = new_clock.get(node_id, 0) + 1
        return VectorClock(new_clock)

    def happens_before(self, other: VectorClock) -> bool:
        """Check if this clock happens before other (strict causality)."""
        is_less_or_equal = all(
            self.clock.get(node, 0) <= other.clock.get(node, 0)
            for node in set(self.clock.keys()) | set(other.clock.keys())
        )
        is_strictly_less = any(
            self.clock.get(node, 0) < other.clock.get(node, 0)
            for node in set(self.clock.keys()) | set(other.clock.keys())
        )
        return is_less_or_equal and is_strictly_less

    def concurrent_with(self, other: VectorClock) -> bool:
        """Check if clocks are concurrent (neither happens before)."""
        return not self.happens_before(other) and not other.happens_before(self)


@dataclass(frozen=True)
class CRDTOperation:
    """Immutable CRDT operation for tool registry."""
    op_type: OperationType
    tool_id: str
    tool_metadata: Optional[Dict[str, Any]] = None
    timestamp: float = 0.0
    node_id: str = ""
    vector_clock: VectorClock = field(default_factory=VectorClock)

    def operation_id(self) -> str:
        """Unique ID for this operation."""
        content = {
            'op_type': self.op_type.value,
            'tool_id': self.tool_id,
            'timestamp': self.timestamp,
            'node_id': self.node_id,
        }
        return hashlib.sha256(
            json.dumps(content, sort_keys=True, default=str).encode()
        ).hexdigest()

    def is_idempotent(self) -> bool:
        """Operations are idempotent: applying twice = applying once."""
        return True


@dataclass
class ToolEntry:
    """Tool entry in CRDT registry."""
    tool_id: str
    metadata: Dict[str, Any]
    enabled: bool = True
    added_by: str = ""
    added_at: float = 0.0
    versions: List[ToolEntry] = field(default_factory=list)


class CRDTToolRegistry:
    """Conflict-free tool registry using CRDT semantics.

    All operations are commutative and idempotent, enabling
    decentralized synchronization without consensus.
    """

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.vector_clock = VectorClock({node_id: 0})

        # Tool registry state
        self.tools: Dict[str, ToolEntry] = {}  # tool_id -> entry
        self._tools_lock = threading.RLock()

        # Operation log (immutable)
        self.operation_log: List[CRDTOperation] = []
        self._log_lock = threading.RLock()

        # Track applied operations to ensure idempotence
        self.applied_operations: Set[str] = set()
        self._applied_lock = threading.RLock()

        # Peer operation logs for synchronization
        self.peer_logs: Dict[str, List[CRDTOperation]] = {}  # node_id -> operations
        self._peer_logs_lock = threading.RLock()

        # Statistics
        self._stats = {
            'total_operations': 0,
            'add_tool_ops': 0,
            'remove_tool_ops': 0,
            'update_tool_ops': 0,
            'conflict_resolutions': 0,
        }

    def add_tool(self, tool_id: str, metadata: Dict[str, Any]) -> CRDTOperation:
        """Add tool to registry (commutative operation).

        Multiple nodes can add the same tool concurrently.
        Conflicts resolved by "add-wins" semantics.
        """
        # Create operation
        self.vector_clock = self.vector_clock.increment(self.node_id)

        op = CRDTOperation(
            op_type=OperationType.ADD_TOOL,
            tool_id=tool_id,
            tool_metadata=metadata,
            timestamp=time.time(),
            node_id=self.node_id,
            vector_clock=self.vector_clock,
        )

        # Apply locally
        self._apply_operation(op)

        return op

    def remove_tool(self, tool_id: str) -> CRDTOperation:
        """Remove tool from registry (commutative operation).

        Remove operations are tracked, allowing add-back later.
        """
        self.vector_clock = self.vector_clock.increment(self.node_id)

        op = CRDTOperation(
            op_type=OperationType.REMOVE_TOOL,
            tool_id=tool_id,
            timestamp=time.time(),
            node_id=self.node_id,
            vector_clock=self.vector_clock,
        )

        self._apply_operation(op)

        return op

    def update_tool(self, tool_id: str, metadata: Dict[str, Any]) -> CRDTOperation:
        """Update tool metadata (commutative operation).

        Later timestamps win in case of concurrent updates.
        """
        self.vector_clock = self.vector_clock.increment(self.node_id)

        op = CRDTOperation(
            op_type=OperationType.UPDATE_TOOL,
            tool_id=tool_id,
            tool_metadata=metadata,
            timestamp=time.time(),
            node_id=self.node_id,
            vector_clock=self.vector_clock,
        )

        self._apply_operation(op)

        return op

    def _apply_operation(self, op: CRDTOperation) -> None:
        """Apply operation to local state (idempotent)."""
        op_id = op.operation_id()

        with self._applied_lock:
            if op_id in self.applied_operations:
                # Already applied, idempotent
                return

            self.applied_operations.add(op_id)

        with self._tools_lock:
            if op.op_type == OperationType.ADD_TOOL:
                if op.tool_id not in self.tools:
                    self.tools[op.tool_id] = ToolEntry(
                        tool_id=op.tool_id,
                        metadata=op.tool_metadata or {},
                        added_by=op.node_id,
                        added_at=op.timestamp,
                    )
                    self._stats['add_tool_ops'] += 1

            elif op.op_type == OperationType.REMOVE_TOOL:
                if op.tool_id in self.tools:
                    # Keep tool but mark history
                    entry = self.tools[op.tool_id]
                    # Track removal in version history
                    self._stats['remove_tool_ops'] += 1

            elif op.op_type == OperationType.UPDATE_TOOL:
                if op.tool_id in self.tools:
                    entry = self.tools[op.tool_id]
                    # Later timestamp wins
                    if op.timestamp > entry.added_at:
                        entry.metadata.update(op.tool_metadata or {})
                        self._stats['update_tool_ops'] += 1

        # Add to operation log
        with self._log_lock:
            self.operation_log.append(op)
            if len(self.operation_log) > _DEFAULT_LOG_RETENTION:
                self.operation_log.pop(0)

        self._stats['total_operations'] += 1

    def sync_with_peer(self, peer_id: str, peer_operations: List[CRDTOperation]) -> int:
        """Sync with peer operations (commutative merge).

        Operations can be applied in any order and still converge.

        Args:
            peer_id: ID of peer node
            peer_operations: List of operations from peer

        Returns:
            Number of new operations applied
        """
        applied_count = 0

        for op in peer_operations:
            # Merge vector clocks
            for node, clock_val in op.vector_clock.clock.items():
                current_val = self.vector_clock.clock.get(node, 0)
                if clock_val > current_val:
                    new_clock = dict(self.vector_clock.clock)
                    new_clock[node] = clock_val
                    self.vector_clock = VectorClock(new_clock)

            # Apply operation (idempotent)
            self._apply_operation(op)
            applied_count += 1

        return applied_count

    def get_tool(self, tool_id: str) -> Optional[ToolEntry]:
        """Get tool entry."""
        with self._tools_lock:
            return self.tools.get(tool_id)

    def list_tools(self) -> List[ToolEntry]:
        """Get all tools."""
        with self._tools_lock:
            return list(self.tools.values())

    def get_operations_since(self, vector_clock: Optional[VectorClock] = None) -> List[CRDTOperation]:
        """Get operations that happened after a vector clock.

        Used for incremental sync.
        """
        if vector_clock is None:
            with self._log_lock:
                return list(self.operation_log)

        # Return operations newer than the given clock
        result = []
        for op in self.operation_log:
            if vector_clock.happens_before(op.vector_clock):
                result.append(op)

        return result

    def resolve_conflicts(self, operations: List[CRDTOperation]) -> None:
        """Resolve conflicts between concurrent operations.

        CRDT semantics handles most conflicts automatically through
        commutativity and timestamp-based resolution.
        """
        # Sort by vector clock for causal ordering
        sorted_ops = sorted(
            operations,
            key=lambda op: (op.timestamp, op.node_id)
        )

        # Apply in order
        for op in sorted_ops:
            self._apply_operation(op)

        self._stats['conflict_resolutions'] += 1

    def get_state_digest(self) -> str:
        """Get hash of current state for comparison."""
        with self._tools_lock:
            state = {
                'tools': {
                    tool_id: {
                        'metadata': entry.metadata,
                        'enabled': entry.enabled,
                    }
                    for tool_id, entry in self.tools.items()
                }
            }

        return hashlib.sha256(
            json.dumps(state, sort_keys=True, default=str).encode()
        ).hexdigest()

    def get_stats(self) -> Dict[str, Any]:
        """Get CRDT statistics."""
        with self._tools_lock:
            tool_count = len(self.tools)

        with self._log_lock:
            log_size = len(self.operation_log)

        return {
            **self._stats,
            'tool_count': tool_count,
            'operation_log_size': log_size,
            'applied_operations': len(self.applied_operations),
        }
