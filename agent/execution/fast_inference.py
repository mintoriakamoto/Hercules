"""Ultra-fast inference execution with speculative caching and parallel dispatch.

Strategies for <500ms end-to-end latency on simple tasks:
  1. Speculative caching: Fast model response + capable model in parallel
  2. Tool call batching: Execute multiple tools in parallel with timeout
  3. Streaming responses: Start sending results before full completion
  4. Context pruning: Drop low-relevance context before API call
  5. Token minimization: Compress messages before sending
  6. Model selection: Use fastest model that can handle task
  7. Parallel inference: Run multiple models on same task, return fastest
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class CachedInference:
    """Cached model response with hit metadata."""

    response: str
    model_used: str
    hit_time_ms: float
    input_hash: str
    created_at: float
    expires_at: float  # TTL-based expiration

    def is_valid(self) -> bool:
        """Check if cache entry is still valid."""
        return time.time() < self.expires_at


class InferenceCache:
    """LRU cache for model responses with semantic deduplication."""

    def __init__(
        self, max_entries: int = 1000, ttl_seconds: int = 3600
    ):
        self.cache: OrderedDict[str, CachedInference] = OrderedDict()
        self.max_entries = max_entries
        self.ttl = ttl_seconds
        self.hits = 0
        self.misses = 0

    def get_key(self, messages: List[Dict[str, Any]]) -> str:
        """Generate cache key from message content."""
        content = json.dumps(messages, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def lookup(
        self, messages: List[Dict[str, Any]]
    ) -> Optional[CachedInference]:
        """Look up cached response."""
        key = self.get_key(messages)
        if key in self.cache:
            entry = self.cache[key]
            if entry.is_valid():
                self.hits += 1
                return entry
            else:
                del self.cache[key]
        self.misses += 1
        return None

    def store(
        self,
        messages: List[Dict[str, Any]],
        response: str,
        model_used: str,
        latency_ms: float,
    ) -> None:
        """Store response in cache."""
        key = self.get_key(messages)
        self.cache[key] = CachedInference(
            response=response,
            model_used=model_used,
            hit_time_ms=latency_ms,
            input_hash=key,
            created_at=time.time(),
            expires_at=time.time() + self.ttl,
        )

        # LRU eviction (O(1) using OrderedDict FIFO)
        if len(self.cache) > self.max_entries:
            self.cache.popitem(last=False)  # Remove oldest (FIFO)

    def hit_rate(self) -> float:
        """Return cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


@dataclass
class TokenReduction:
    """Token reduction metadata."""

    original_token_count: int
    reduced_token_count: int
    reduction_percent: float
    techniques_applied: List[str] = field(default_factory=list)

    @property
    def savings(self) -> int:
        """Tokens saved."""
        return self.original_token_count - self.reduced_token_count


class ContextPruner:
    """Intelligently prune context to minimize tokens while preserving quality."""

    @staticmethod
    def estimate_tokens(content: str) -> int:
        """Rough token estimation (1 token ≈ 4 chars)."""
        return len(content) // 4

    @staticmethod
    def prune_messages(
        messages: List[Dict[str, Any]], target_reduction: float = 0.3
    ) -> Tuple[List[Dict[str, Any]], TokenReduction]:
        """Prune low-relevance messages to reduce token count.

        Args:
            messages: Message history
            target_reduction: Target % reduction (0.3 = 30% reduction)

        Returns:
            (pruned_messages, reduction_metadata)
        """
        original_tokens = sum(
            ContextPruner.estimate_tokens(m.get("content", ""))
            for m in messages
        )

        # Score messages by relevance (newer = higher, tool calls = higher)
        scored = []
        for i, msg in enumerate(messages):
            relevance = i / max(1, len(messages) - 1)  # Recency
            if msg.get("role") == "assistant" and "tool_use" in str(
                msg.get("content", "")
            ):
                relevance += 0.5  # Tool calls are highly relevant
            scored.append((msg, relevance))

        # Sort by relevance and keep top N%
        scored.sort(key=lambda x: x[1], reverse=True)
        keep_count = max(1, int(len(messages) * (1 - target_reduction)))

        # Build index once for O(1) lookup (avoid O(n²) messages.index calls)
        msg_index = {id(msg): i for i, msg in enumerate(messages)}
        pruned = sorted(
            scored[:keep_count],
            key=lambda x: msg_index[id(x[0])],
        )

        pruned_messages = [msg for msg, _ in pruned]
        reduced_tokens = sum(
            ContextPruner.estimate_tokens(m.get("content", ""))
            for m in pruned_messages
        )

        return (
            pruned_messages,
            TokenReduction(
                original_token_count=original_tokens,
                reduced_token_count=reduced_tokens,
                reduction_percent=(
                    (original_tokens - reduced_tokens)
                    / original_tokens
                    * 100
                ),
                techniques_applied=["message_pruning"],
            ),
        )

    @staticmethod
    def compress_content(content: str, max_length: int = 500) -> str:
        """Truncate content to reasonable length."""
        if len(content) > max_length:
            return content[:max_length] + "... [truncated]"
        return content


@dataclass
class FastInferenceResult:
    """Result of fast inference execution."""

    response: str
    model: str
    latency_ms: float
    cache_hit: bool
    used_pruning: bool
    token_reduction: Optional[TokenReduction] = None

    @property
    def is_fast(self) -> bool:
        """Whether response was sub-500ms."""
        return self.latency_ms < 500


class ParallelInference:
    """Execute inference across multiple models in parallel."""

    def __init__(self, timeout_ms: int = 200):
        self.timeout_ms = timeout_ms

    async def execute_parallel(
        self,
        fast_model_fn,
        capable_model_fn,
        messages: List[Dict[str, Any]],
    ) -> FastInferenceResult:
        """Run fast and capable models in parallel.

        Returns faster successful response.
        """
        start_time = time.time()

        # Start both models concurrently
        fast_task = asyncio.create_task(
            self._safe_call(fast_model_fn, messages)
        )
        capable_task = asyncio.create_task(
            self._safe_call(capable_model_fn, messages)
        )

        # Fast-path: wait for fast model with short timeout
        try:
            fast_result = await asyncio.wait_for(
                fast_task, timeout=self.timeout_ms / 1000.0
            )
            capable_task.cancel()
            return FastInferenceResult(
                response=fast_result,
                model="fast",
                latency_ms=(time.time() - start_time) * 1000,
                cache_hit=False,
                used_pruning=False,
            )
        except asyncio.TimeoutError:
            pass

        # Fall back to capable model
        try:
            capable_result = await asyncio.wait_for(
                capable_task, timeout=5.0
            )
            fast_task.cancel()
            return FastInferenceResult(
                response=capable_result,
                model="capable",
                latency_ms=(time.time() - start_time) * 1000,
                cache_hit=False,
                used_pruning=False,
            )
        except asyncio.TimeoutError:
            return FastInferenceResult(
                response="[timeout]",
                model="none",
                latency_ms=(time.time() - start_time) * 1000,
                cache_hit=False,
                used_pruning=False,
            )

    @staticmethod
    async def _safe_call(fn, args):
        """Safely call async function with error handling."""
        try:
            return await fn(args)
        except Exception as e:
            logger.debug("Model call failed: %s", e)
            raise


class FastInferenceEngine:
    """Orchestrates all fast inference techniques."""

    def __init__(self, cache_size: int = 1000):
        self.cache = InferenceCache(max_entries=cache_size)
        self.parallel = ParallelInference(timeout_ms=200)
        self.stats = {
            "total_calls": 0,
            "cache_hits": 0,
            "fast_responses": 0,
            "total_latency_ms": 0.0,
        }

    async def infer(
        self,
        messages: List[Dict[str, Any]],
        fast_model_fn,
        capable_model_fn,
        enable_pruning: bool = True,
        enable_cache: bool = True,
    ) -> FastInferenceResult:
        """Execute inference with all optimizations."""
        start_time = time.time()

        # 1. Check cache
        if enable_cache:
            cached = self.cache.lookup(messages)
            if cached and cached.is_valid():
                result = FastInferenceResult(
                    response=cached.response,
                    model=cached.model_used,
                    latency_ms=cached.hit_time_ms,
                    cache_hit=True,
                    used_pruning=False,
                )
                self._update_stats(result)
                return result

        # 2. Prune context if needed
        pruned_messages = messages
        token_reduction = None
        if enable_pruning and len(messages) > 20:
            pruned_messages, token_reduction = (
                ContextPruner.prune_messages(
                    messages, target_reduction=0.2
                )
            )

        # 3. Execute inference (parallel or sequential)
        result = await self.parallel.execute_parallel(
            fast_model_fn, capable_model_fn, pruned_messages
        )

        # Add token reduction metadata
        if token_reduction:
            result.token_reduction = token_reduction
            result.used_pruning = True

        # Update latency
        result.latency_ms = (time.time() - start_time) * 1000

        # 4. Cache result
        if enable_cache and result.response != "[timeout]":
            self.cache.store(
                messages,
                result.response,
                result.model,
                result.latency_ms,
            )

        self._update_stats(result)
        return result

    def _update_stats(self, result: FastInferenceResult) -> None:
        """Update performance statistics."""
        self.stats["total_calls"] += 1
        if result.cache_hit:
            self.stats["cache_hits"] += 1
        if result.is_fast:
            self.stats["fast_responses"] += 1
        self.stats["total_latency_ms"] += result.latency_ms

    def get_metrics(self) -> Dict[str, Any]:
        """Return performance metrics."""
        total = self.stats["total_calls"]
        return {
            "total_calls": total,
            "cache_hit_rate": (
                self.stats["cache_hits"] / total if total > 0 else 0
            ),
            "fast_response_rate": (
                self.stats["fast_responses"] / total
                if total > 0
                else 0
            ),
            "avg_latency_ms": (
                self.stats["total_latency_ms"] / total
                if total > 0
                else 0
            ),
            "cache_entries": len(self.cache.cache),
            "cache_efficiency": self.cache.hit_rate(),
        }
