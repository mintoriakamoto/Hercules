#!/usr/bin/env python3
"""
Tool Pool Manager — Connection pooling and health management.

Maintains persistent connection pools to remote dispatch nodes with:
  - Connection reuse to avoid handshake overhead
  - Heartbeat/health checks for failure detection
  - Backpressure handling and queue management
  - Exponential backoff on failures
  - Metrics collection per pool

Architecture:
  - ToolPool: manages connections to one remote node
  - ToolPoolCluster: manages multiple pools (one per node)
  - Request queues with backpressure
  - Health monitoring with exponential backoff
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
from collections import deque
import socket

logger = logging.getLogger(__name__)

# Configuration
_DEFAULT_POOL_SIZE = 10
_DEFAULT_HEARTBEAT_INTERVAL = 5.0
_DEFAULT_HEALTH_CHECK_TIMEOUT = 2.0
_DEFAULT_MAX_QUEUE_SIZE = 10000
_DEFAULT_BACKOFF_BASE = 1.0  # seconds
_DEFAULT_BACKOFF_MAX = 60.0  # seconds


class PoolHealthStatus(Enum):
    """Health status of a connection pool."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    RECOVERING = "recovering"


@dataclass
class PoolMetrics:
    """Metrics for a connection pool."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    queued_requests: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    health_check_failures: int = 0
    last_health_check: float = field(default_factory=time.time)
    connection_errors: int = 0


@dataclass
class PoolConnection:
    """Represents a single connection in the pool."""
    connection_id: str
    host: str
    port: int
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    is_open: bool = True
    total_requests: int = 0
    failed_requests: int = 0

    def get_age_seconds(self) -> float:
        """Get connection age in seconds."""
        return time.time() - self.created_at

    def get_idle_seconds(self) -> float:
        """Get idle time in seconds."""
        return time.time() - self.last_used


class ToolPool:
    """Connection pool to a single remote tool dispatch node.

    Manages a fixed-size pool of TCP connections with health checks,
    request queuing, and backoff.
    """

    def __init__(self, host: str, port: int, pool_size: int = _DEFAULT_POOL_SIZE,
                 max_queue_size: int = _DEFAULT_MAX_QUEUE_SIZE,
                 heartbeat_interval: float = _DEFAULT_HEARTBEAT_INTERVAL):
        self.host = host
        self.port = port
        self.pool_size = pool_size
        self.max_queue_size = max_queue_size
        self.heartbeat_interval = heartbeat_interval

        # Connection management
        self.available_connections: deque[PoolConnection] = deque()
        self.active_connections: Dict[str, PoolConnection] = {}
        self._conn_lock = threading.RLock()

        # Request queue
        self.request_queue: queue.Queue = queue.Queue(maxsize=max_queue_size)
        self._process_thread = None
        self._stop_processing = False

        # Health tracking
        self.status = PoolHealthStatus.HEALTHY
        self.consecutive_failures = 0
        self.backoff_until = 0.0
        self.current_backoff_ms = _DEFAULT_BACKOFF_BASE

        # Metrics
        self.metrics = PoolMetrics()
        self._latencies: deque = deque(maxlen=1000)  # Rolling window

        # Initialization
        self._initialize_pool()

    def _initialize_pool(self) -> None:
        """Initialize the connection pool."""
        with self._conn_lock:
            for i in range(self.pool_size):
                conn = PoolConnection(
                    connection_id=f"{self.host}:{self.port}:conn{i}",
                    host=self.host,
                    port=self.port
                )
                self.available_connections.append(conn)

        logger.info(
            f"Initialized pool to {self.host}:{self.port} with {self.pool_size} connections"
        )

    def acquire_connection(self, timeout_seconds: float = 5.0) -> Optional[PoolConnection]:
        """Acquire a connection from the pool.

        Returns a connection or None if pool is exhausted/unhealthy.
        """
        # Check if in backoff period
        if self.status == PoolHealthStatus.UNHEALTHY:
            if time.time() < self.backoff_until:
                return None
            else:
                self.status = PoolHealthStatus.RECOVERING

        start = time.time()

        with self._conn_lock:
            while time.time() - start < timeout_seconds:
                if self.available_connections:
                    conn = self.available_connections.popleft()
                    self.active_connections[conn.connection_id] = conn
                    conn.last_used = time.time()
                    self.metrics.active_connections = len(self.active_connections)
                    self.metrics.idle_connections = len(self.available_connections)
                    return conn

                # Wait for connection to become available
                time.sleep(0.01)

        logger.warning(
            f"Failed to acquire connection from {self.host}:{self.port} within {timeout_seconds}s"
        )
        self.metrics.connection_errors += 1
        return None

    def release_connection(self, conn: PoolConnection, success: bool = True) -> None:
        """Release a connection back to the pool.

        Args:
            conn: Connection to release
            success: Whether the last operation on this connection succeeded
        """
        with self._conn_lock:
            if conn.connection_id in self.active_connections:
                del self.active_connections[conn.connection_id]

            if success:
                conn.failed_requests = 0
                self.available_connections.append(conn)
                self.consecutive_failures = 0

                if self.status == PoolHealthStatus.RECOVERING:
                    self.status = PoolHealthStatus.HEALTHY
                    self.current_backoff_ms = _DEFAULT_BACKOFF_BASE
            else:
                conn.failed_requests += 1
                self.consecutive_failures += 1

                # Close connection on repeated failures
                if conn.failed_requests > 3:
                    conn.is_open = False
                    # Could reconnect here, but for now drop it
                else:
                    self.available_connections.append(conn)

                # Trigger backoff if too many consecutive failures
                if self.consecutive_failures >= 3:
                    self.status = PoolHealthStatus.UNHEALTHY
                    self.backoff_until = time.time() + self.current_backoff_ms / 1000.0
                    self.current_backoff_ms = min(
                        self.current_backoff_ms * 2,
                        _DEFAULT_BACKOFF_MAX * 1000
                    )
                    logger.error(
                        f"Pool {self.host}:{self.port} marked UNHEALTHY after "
                        f"{self.consecutive_failures} failures; backoff {self.current_backoff_ms}ms"
                    )

            self.metrics.active_connections = len(self.active_connections)
            self.metrics.idle_connections = len(self.available_connections)

    def execute_request(self, request: Any, timeout_ms: float = 30000.0) -> Tuple[bool, Any]:
        """Execute a request on this pool.

        Returns (success, result) tuple.
        """
        conn = self.acquire_connection(timeout_seconds=timeout_ms / 1000.0)

        if not conn:
            self.metrics.failed_requests += 1
            return False, "No connection available"

        start = time.time()

        try:
            # In real implementation, this would send request over socket
            # and read response. For now, simulate execution.

            # Simulate network latency
            time.sleep(0.001)

            latency_ms = (time.time() - start) * 1000
            self._latencies.append(latency_ms)
            self._update_latency_stats()

            conn.total_requests += 1
            self.metrics.total_requests += 1
            self.metrics.successful_requests += 1

            self.release_connection(conn, success=True)
            return True, {"status": "ok"}

        except Exception as e:
            logger.warning(f"Request failed on {self.host}:{self.port}: {e}")
            conn.failed_requests += 1
            self.metrics.failed_requests += 1
            self.release_connection(conn, success=False)
            return False, str(e)

    def _update_latency_stats(self) -> None:
        """Update p95/p99 latency statistics."""
        if not self._latencies:
            return

        sorted_latencies = sorted(self._latencies)
        n = len(sorted_latencies)

        self.metrics.avg_latency_ms = sum(sorted_latencies) / n
        self.metrics.p95_latency_ms = sorted_latencies[int(n * 0.95)]
        self.metrics.p99_latency_ms = sorted_latencies[int(n * 0.99)]

    def health_check(self) -> bool:
        """Perform health check on this pool.

        Returns True if pool is healthy.
        """
        conn = self.acquire_connection(timeout_seconds=_DEFAULT_HEALTH_CHECK_TIMEOUT)

        if not conn:
            self.metrics.health_check_failures += 1
            self.metrics.last_health_check = time.time()
            return False

        try:
            # In real implementation, send health check request
            # For now, simulate with timing
            time.sleep(0.0001)

            self.release_connection(conn, success=True)
            self.metrics.last_health_check = time.time()
            return True

        except Exception as e:
            logger.warning(f"Health check failed for {self.host}:{self.port}: {e}")
            self.metrics.health_check_failures += 1
            self.release_connection(conn, success=False)
            return False

    def get_metrics(self) -> PoolMetrics:
        """Get pool metrics."""
        with self._conn_lock:
            metrics = PoolMetrics(
                total_requests=self.metrics.total_requests,
                successful_requests=self.metrics.successful_requests,
                failed_requests=self.metrics.failed_requests,
                queued_requests=self.request_queue.qsize(),
                active_connections=len(self.active_connections),
                idle_connections=len(self.available_connections),
                avg_latency_ms=self.metrics.avg_latency_ms,
                p95_latency_ms=self.metrics.p95_latency_ms,
                p99_latency_ms=self.metrics.p99_latency_ms,
                health_check_failures=self.metrics.health_check_failures,
                last_health_check=self.metrics.last_health_check,
                connection_errors=self.metrics.connection_errors,
            )
            return metrics

    def shutdown(self) -> None:
        """Shutdown the pool and close connections."""
        self._stop_processing = True

        with self._conn_lock:
            for conn in self.available_connections:
                conn.is_open = False

            for conn in self.active_connections.values():
                conn.is_open = False

        logger.info(f"Pool {self.host}:{self.port} shutdown")


class ToolPoolCluster:
    """Manages multiple connection pools (one per dispatch node).

    Coordinates health checks across pools and load balancing.
    """

    def __init__(self, pool_size: int = _DEFAULT_POOL_SIZE):
        self.pool_size = pool_size
        self.pools: Dict[str, ToolPool] = {}
        self._pools_lock = threading.RLock()

        self._health_check_thread = None
        self._stop_health_checks = False

    def add_pool(self, pool_id: str, host: str, port: int) -> ToolPool:
        """Add a new pool to the cluster."""
        with self._pools_lock:
            if pool_id in self.pools:
                return self.pools[pool_id]

            pool = ToolPool(host, port, pool_size=self.pool_size)
            self.pools[pool_id] = pool
            return pool

    def get_pool(self, pool_id: str) -> Optional[ToolPool]:
        """Get a pool by ID."""
        with self._pools_lock:
            return self.pools.get(pool_id)

    def start_health_checks(self, interval_seconds: float = _DEFAULT_HEARTBEAT_INTERVAL) -> None:
        """Start background health check thread."""
        if self._health_check_thread:
            return

        def health_check_loop():
            while not self._stop_health_checks:
                with self._pools_lock:
                    for pool in list(self.pools.values()):
                        pool.health_check()

                time.sleep(interval_seconds)

        self._health_check_thread = threading.Thread(
            target=health_check_loop, daemon=True
        )
        self._health_check_thread.start()
        logger.info(f"Started cluster health checks (interval={interval_seconds}s)")

    def stop_health_checks(self) -> None:
        """Stop health check thread."""
        self._stop_health_checks = True
        if self._health_check_thread:
            self._health_check_thread.join(timeout=5)

    def get_cluster_metrics(self) -> Dict[str, Any]:
        """Get metrics across all pools."""
        with self._pools_lock:
            total_metrics = {
                'pools': {},
                'total_requests': 0,
                'total_failures': 0,
                'healthy_pools': 0,
                'unhealthy_pools': 0,
            }

            for pool_id, pool in self.pools.items():
                metrics = pool.get_metrics()
                total_metrics['pools'][pool_id] = {
                    'status': pool.status.value,
                    'total_requests': metrics.total_requests,
                    'failed_requests': metrics.failed_requests,
                    'active_connections': metrics.active_connections,
                    'idle_connections': metrics.idle_connections,
                    'avg_latency_ms': metrics.avg_latency_ms,
                    'p99_latency_ms': metrics.p99_latency_ms,
                }

                total_metrics['total_requests'] += metrics.total_requests
                total_metrics['total_failures'] += metrics.failed_requests

                if pool.status == PoolHealthStatus.HEALTHY:
                    total_metrics['healthy_pools'] += 1
                else:
                    total_metrics['unhealthy_pools'] += 1

            return total_metrics

    def shutdown(self) -> None:
        """Shutdown all pools."""
        self.stop_health_checks()

        with self._pools_lock:
            for pool in self.pools.values():
                pool.shutdown()
            self.pools.clear()

        logger.info("ToolPoolCluster shutdown")
