"""Batch and parallelize tool call execution for sub-100ms latency.

Strategies:
  1. Parallel execution: Run non-dependent tools concurrently
  2. Dependency detection: Identify tool call DAG
  3. Timeout management: Fast fail if tool exceeds latency budget
  4. Result caching: Memoize tool results
  5. Streaming results: Return partial results as they complete
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    """Represents a single tool invocation."""

    id: str
    name: str
    arguments: Dict[str, Any]
    depends_on: Set[str]  # Tool IDs this depends on
    timeout_ms: int = 5000

    def get_cache_key(self) -> str:
        """Generate cache key from tool name and args."""
        content = json.dumps(
            {"name": self.name, "args": self.arguments},
            sort_keys=True,
        )
        return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class ToolResult:
    """Result of a tool execution."""

    tool_id: str
    tool_name: str
    result: Any
    latency_ms: float
    cache_hit: bool = False
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        """Whether tool executed successfully."""
        return self.error is None


class ToolDependencyGraph:
    """Build and analyze tool call dependency graph."""

    def __init__(self, calls: List[ToolCall]):
        self.calls = {c.id: c for c in calls}

    def get_execution_order(self) -> List[List[str]]:
        """Return batches of tool IDs that can execute in parallel.

        Returns:
            List of batches, where each batch contains tool IDs
            that can execute concurrently.
        """
        # Topological sort with batch grouping
        remaining = set(self.calls.keys())
        batches = []

        while remaining:
            # Find all tools with satisfied dependencies
            batch = {
                tid
                for tid in remaining
                if self.calls[tid].depends_on.isdisjoint(remaining)
            }

            if not batch:
                # Circular dependency - break it
                batch = {remaining.pop()}
                remaining.add(list(batch)[0])
                logger.warning(
                    f"Circular dependency detected, breaking at {batch}"
                )

            batches.append(sorted(list(batch)))
            remaining -= batch

        return batches

    def is_parallelizable(self, tool_ids: List[str]) -> bool:
        """Check if tools can run in parallel."""
        # Tools can run in parallel if they have no dependencies
        # or depend only on tools outside this set
        for tid in tool_ids:
            for other_id in tool_ids:
                if tid != other_id:
                    if other_id in self.calls[tid].depends_on:
                        return False
        return True


class ToolResultCache:
    """Cache tool results to avoid re-execution."""

    def __init__(self, max_entries: int = 500, ttl_seconds: int = 3600):
        self.cache: OrderedDict[str, Tuple[Any, float]] = OrderedDict()
        self.max_entries = max_entries
        self.ttl = ttl_seconds
        self.hits = 0
        self.misses = 0

    def get(self, cache_key: str) -> Optional[Any]:
        """Retrieve cached result."""
        if cache_key in self.cache:
            result, created_at = self.cache[cache_key]
            if time.time() - created_at < self.ttl:
                self.hits += 1
                return result
            else:
                del self.cache[cache_key]
        self.misses += 1
        return None

    def set(self, cache_key: str, result: Any) -> None:
        """Store result in cache."""
        self.cache[cache_key] = (result, time.time())
        if len(self.cache) > self.max_entries:
            # Remove oldest entry (O(1) using OrderedDict FIFO)
            self.cache.popitem(last=False)

    def hit_rate(self) -> float:
        """Return cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class ParallelToolExecutor:
    """Execute tool calls in parallel with dependency awareness."""

    def __init__(
        self,
        tool_executors: Dict[str, Callable],
        cache_size: int = 500,
        max_parallel_tools: int = 16,
    ):
        """Initialize executor.

        Args:
            tool_executors: Map of tool name to async executor function
            cache_size: Max cached results
            max_parallel_tools: Max concurrent tool executions
        """
        self.tool_executors = tool_executors
        self.cache = ToolResultCache(max_entries=cache_size)
        self.semaphore = asyncio.Semaphore(max_parallel_tools)
        self.stats = {
            "total_calls": 0,
            "cache_hits": 0,
            "total_latency_ms": 0.0,
            "max_parallel_latency_ms": 0.0,
        }

    async def execute_batch(
        self, calls: List[ToolCall]
    ) -> Dict[str, ToolResult]:
        """Execute tool calls with parallelization.

        Args:
            calls: List of tool calls to execute

        Returns:
            Map of tool_id -> ToolResult
        """
        start_time = time.time()

        # Build dependency graph
        graph = ToolDependencyGraph(calls)
        batches = graph.get_execution_order()

        results: Dict[str, ToolResult] = {}

        # Execute each batch
        for batch in batches:
            batch_tasks = [
                self._execute_tool(calls[cid], results)
                for cid in batch
            ]
            batch_results = await asyncio.gather(
                *batch_tasks, return_exceptions=True
            )

            # Store results and handle errors
            for tool_id, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    results[tool_id] = ToolResult(
                        tool_id=tool_id,
                        tool_name=calls[tool_id].name,
                        result=None,
                        latency_ms=0,
                        error=str(result),
                    )
                else:
                    results[tool_id] = result

        elapsed_ms = (time.time() - start_time) * 1000
        self._update_stats(results, elapsed_ms)
        return results

    async def _execute_tool(
        self,
        call: ToolCall,
        prior_results: Dict[str, ToolResult],
    ) -> ToolResult:
        """Execute a single tool call with caching."""
        start_time = time.time()

        # Check cache
        cache_key = call.get_cache_key()
        cached = self.cache.get(cache_key)
        if cached is not None:
            return ToolResult(
                tool_id=call.id,
                tool_name=call.name,
                result=cached,
                latency_ms=(time.time() - start_time) * 1000,
                cache_hit=True,
            )

        # Get executor
        if call.name not in self.tool_executors:
            return ToolResult(
                tool_id=call.id,
                tool_name=call.name,
                result=None,
                latency_ms=0,
                error=f"Unknown tool: {call.name}",
            )

        executor = self.tool_executors[call.name]

        # Execute with timeout and semaphore
        try:
            async with self.semaphore:
                result = await asyncio.wait_for(
                    executor(call.arguments),
                    timeout=call.timeout_ms / 1000.0,
                )

            # Cache result
            self.cache.set(cache_key, result)

            return ToolResult(
                tool_id=call.id,
                tool_name=call.name,
                result=result,
                latency_ms=(time.time() - start_time) * 1000,
            )

        except asyncio.TimeoutError:
            return ToolResult(
                tool_id=call.id,
                tool_name=call.name,
                result=None,
                latency_ms=(time.time() - start_time) * 1000,
                error=f"Timeout after {call.timeout_ms}ms",
            )
        except Exception as e:
            return ToolResult(
                tool_id=call.id,
                tool_name=call.name,
                result=None,
                latency_ms=(time.time() - start_time) * 1000,
                error=f"Execution error: {str(e)}",
            )

    def _update_stats(
        self,
        results: Dict[str, ToolResult],
        total_latency_ms: float,
    ) -> None:
        """Update execution statistics."""
        self.stats["total_calls"] += len(results)
        self.stats["cache_hits"] += sum(
            1 for r in results.values() if r.cache_hit
        )
        self.stats["total_latency_ms"] += total_latency_ms
        self.stats["max_parallel_latency_ms"] = max(
            self.stats["max_parallel_latency_ms"],
            max(
                (r.latency_ms for r in results.values()),
                default=0,
            ),
        )

    def get_metrics(self) -> Dict[str, Any]:
        """Return performance metrics."""
        total = self.stats["total_calls"]
        return {
            "total_tool_calls": total,
            "cache_hit_rate": (
                self.stats["cache_hits"] / total if total > 0 else 0
            ),
            "avg_call_latency_ms": (
                self.stats["total_latency_ms"] / total
                if total > 0
                else 0
            ),
            "max_parallel_latency_ms": (
                self.stats["max_parallel_latency_ms"]
            ),
            "cache_entries": len(self.cache.cache),
            "cache_efficiency": self.cache.hit_rate(),
        }
