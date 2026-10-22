#!/usr/bin/env python3
"""Memory pooling and pre-allocation for tool buffers.

Pre-allocates tool argument/result buffers, reuses memory across calls
(eliminates GC pauses), maintains NUMA-local memory pools.
Target: 2-4x speedup (eliminate allocation overhead).

Enables: memory_pooling (bool), pool_size_mb (int)
"""

import json
import logging
import os
import threading
from collections import deque
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MemoryPool:
    """Pre-allocated buffer pool for tool arguments and results."""

    def __init__(self, pool_size_mb: int = 256, buffer_size: int = 65536):
        self.pool_size_mb = pool_size_mb
        self.buffer_size = buffer_size
        self.max_buffers = max(1, (pool_size_mb * 1024 * 1024) // buffer_size)

        # Pool of available buffers
        self.available: deque = deque()
        self.in_use: Dict[int, bytearray] = {}

        # Statistics
        self.allocations = 0
        self.reuses = 0
        self.gc_pauses_avoided = 0

        self._lock = threading.Lock()

        # Pre-allocate buffers
        self._initialize_pool()

    def _initialize_pool(self) -> None:
        """Pre-allocate buffer pool."""
        for _ in range(min(10, self.max_buffers)):
            buf = bytearray(self.buffer_size)
            self.available.append(buf)
            # Touch memory to localize to NUMA node
            for i in range(0, len(buf), 4096):
                buf[i] = 0

    def acquire(self, size: int) -> bytearray:
        """Get a buffer from pool or allocate new one."""
        with self._lock:
            if self.available:
                buf = self.available.popleft()
                self.reuses += 1
                if len(buf) >= size:
                    return buf
                else:
                    # Buffer too small; allocate new one
                    self.allocations += 1
                    return bytearray(size)

            self.allocations += 1
            # Track allocation for later return
            buf = bytearray(size)
            return buf

    def release(self, buf: bytearray) -> None:
        """Return buffer to pool."""
        with self._lock:
            if len(self.available) < self.max_buffers and len(buf) <= self.buffer_size:
                # Clear buffer for reuse
                buf[:] = b"\0" * len(buf)
                self.available.append(buf)
                self.gc_pauses_avoided += 1

    def get_stats(self) -> Dict[str, int]:
        """Get pool statistics."""
        with self._lock:
            return {
                "available_buffers": len(self.available),
                "allocations": self.allocations,
                "reuses": self.reuses,
                "gc_pauses_avoided": self.gc_pauses_avoided,
            }


class NUMAMemoryPool:
    """NUMA-aware memory pooling with per-node pools."""

    def __init__(self, num_nodes: int = 1, pool_size_mb: int = 256):
        self.num_nodes = num_nodes
        self.pools: Dict[int, MemoryPool] = {}

        # Create pool per NUMA node
        for node_id in range(num_nodes):
            self.pools[node_id] = MemoryPool(pool_size_mb // max(1, num_nodes))

        self._lock = threading.Lock()

    def acquire(self, size: int, numa_node: int = 0) -> bytearray:
        """Acquire buffer from NUMA node's pool."""
        node = numa_node % self.num_nodes
        pool = self.pools.get(node, self.pools[0])
        return pool.acquire(size)

    def release(self, buf: bytearray, numa_node: int = 0) -> None:
        """Return buffer to NUMA node's pool."""
        node = numa_node % self.num_nodes
        pool = self.pools.get(node, self.pools[0])
        pool.release(buf)

    def get_stats(self) -> Dict[str, Any]:
        """Get stats from all pools."""
        stats = {}
        for node_id, pool in self.pools.items():
            stats[f"node_{node_id}"] = pool.get_stats()
        return stats


class ToolArgumentPool:
    """Pool for serialized tool arguments (JSON objects)."""

    def __init__(self, num_slots: int = 1000):
        self.num_slots = num_slots
        self.available: deque = deque(maxlen=num_slots)
        self.hits = 0
        self.misses = 0
        self._lock = threading.Lock()

    def get_buffer_for_args(self, args: Dict[str, Any]) -> bytearray:
        """Get buffer for argument serialization."""
        estimated_size = len(json.dumps(args).encode("utf-8")) + 256
        with self._lock:
            if self.available:
                buf = self.available.popleft()
                if len(buf) >= estimated_size:
                    self.hits += 1
                    return buf
                self.misses += 1
            else:
                self.misses += 1

        return bytearray(estimated_size)

    def release_buffer(self, buf: bytearray) -> None:
        """Return argument buffer to pool."""
        with self._lock:
            if len(self.available) < self.num_slots:
                self.available.append(buf)


class ResultBufferPool:
    """Pool for tool result buffers (string/JSON results)."""

    def __init__(self, num_slots: int = 500, buffer_size_kb: int = 256):
        self.num_slots = num_slots
        self.buffer_size = buffer_size_kb * 1024
        self.available: deque = deque(maxlen=num_slots)
        self.hits = 0
        self.misses = 0
        self._lock = threading.Lock()

        # Pre-allocate some buffers
        for _ in range(min(10, num_slots)):
            self.available.append(bytearray(self.buffer_size))

    def acquire(self) -> bytearray:
        """Get result buffer."""
        with self._lock:
            if self.available:
                self.hits += 1
                return self.available.popleft()
            self.misses += 1

        return bytearray(self.buffer_size)

    def release(self, buf: bytearray) -> None:
        """Return result buffer."""
        with self._lock:
            if len(self.available) < self.num_slots:
                # Clear for reuse
                buf[:] = b"\0" * len(buf)
                self.available.append(buf)

    def get_stats(self) -> Dict[str, int]:
        """Get pool statistics."""
        with self._lock:
            return {
                "available": len(self.available),
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate_percent": 100 * self.hits // max(1, self.hits + self.misses),
            }


# Global pools
_memory_pool: Optional[NUMAMemoryPool] = None
_arg_pool: Optional[ToolArgumentPool] = None
_result_pool: Optional[ResultBufferPool] = None
_pools_lock = threading.Lock()


def initialize_pools(
    num_numa_nodes: int = 1,
    pool_size_mb: int = 256,
) -> None:
    """Initialize global memory pools."""
    global _memory_pool, _arg_pool, _result_pool

    with _pools_lock:
        if _memory_pool is None:
            _memory_pool = NUMAMemoryPool(num_numa_nodes, pool_size_mb)
            _arg_pool = ToolArgumentPool()
            _result_pool = ResultBufferPool()
            logger.info(
                "Initialized memory pools: %d NUMA nodes, %d MB total",
                num_numa_nodes,
                pool_size_mb,
            )


def get_memory_pool() -> Optional[NUMAMemoryPool]:
    """Get global memory pool."""
    if _memory_pool is None:
        initialize_pools()
    return _memory_pool


def get_arg_pool() -> Optional[ToolArgumentPool]:
    """Get global argument pool."""
    if _arg_pool is None:
        initialize_pools()
    return _arg_pool


def get_result_pool() -> Optional[ResultBufferPool]:
    """Get global result pool."""
    if _result_pool is None:
        initialize_pools()
    return _result_pool


def acquire_arg_buffer(args: Dict[str, Any]) -> bytearray:
    """Acquire buffer for tool arguments."""
    pool = get_arg_pool()
    if pool:
        return pool.get_buffer_for_args(args)
    return bytearray()


def release_arg_buffer(buf: bytearray) -> None:
    """Return argument buffer."""
    pool = get_arg_pool()
    if pool:
        pool.release_buffer(buf)


def acquire_result_buffer() -> bytearray:
    """Acquire buffer for tool result."""
    pool = get_result_pool()
    if pool:
        return pool.acquire()
    return bytearray(65536)


def release_result_buffer(buf: bytearray) -> None:
    """Return result buffer."""
    pool = get_result_pool()
    if pool:
        pool.release(buf)


def get_pool_stats() -> Dict[str, Any]:
    """Get statistics from all pools."""
    stats = {
        "memory_pool": get_memory_pool().get_stats() if get_memory_pool() else {},
        "result_pool": get_result_pool().get_stats() if get_result_pool() else {},
    }
    return stats
