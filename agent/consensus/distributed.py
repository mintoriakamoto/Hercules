#!/usr/bin/env python3
"""
Distributed Consensus Extension for Tool Call Verification

Extends the single-node consensus system to work across distributed
dispatch nodes. Handles:

  - Deterministic tool result validation across nodes
  - Cached proofs for hot tools (avoid re-verification)
  - Quorum-based verification for critical operations
  - Cross-node proof replay

Key differences from local consensus:
  - Multiple nodes may perform identical tool calls (for replication)
  - Results must be comparable deterministically (exact equality or hash)
  - Network delays add complexity to proof replay
  - Failed nodes still participate in consensus if results are cached
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Configuration
_DEFAULT_QUORUM_SIZE = 3
_DEFAULT_PROOF_CACHE_TTL_SECONDS = 3600  # 1 hour
_DEFAULT_ALLOW_partial_quorum = False


@dataclass(frozen=True)
class DistributedVerification:
    """Result of distributed consensus verification."""
    is_verified: bool
    agreeing_nodes: List[str]
    disagreeing_nodes: List[str]
    quorum_size: int
    verification_time_ms: float
    error: Optional[str] = None


@dataclass(frozen=True)
class ToolResultHash:
    """Deterministic hash of a tool result for cross-node comparison."""
    tool_name: str
    args_hash: str
    result_hash: str
    timestamp: float


class ProofCache:
    """Caches validation results for tool calls across nodes.

    Avoids redundant verification for hot tools by storing validation
    results with TTL. Invalidated on tool schema changes.
    """

    def __init__(self, ttl_seconds: float = _DEFAULT_PROOF_CACHE_TTL_SECONDS):
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, Tuple[bool, float]] = {}  # proof_hash -> (is_valid, timestamp)
        self._lock = threading.RLock()

    def store(self, proof_hash: str, is_valid: bool) -> None:
        """Store validation result for a proof."""
        with self._lock:
            self.cache[proof_hash] = (is_valid, time.time())

    def get(self, proof_hash: str) -> Optional[bool]:
        """Get cached validation result if still valid."""
        with self._lock:
            if proof_hash not in self.cache:
                return None

            is_valid, ts = self.cache[proof_hash]

            if time.time() - ts > self.ttl_seconds:
                del self.cache[proof_hash]
                return None

            return is_valid

    def invalidate_tool(self, tool_name: str) -> None:
        """Invalidate all proofs for a tool (after schema change)."""
        with self._lock:
            # In production, would need to track which proofs are for which tools
            # For now, clear cache on any tool change
            self.cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            return {
                'cached_proofs': len(self.cache),
                'ttl_seconds': self.ttl_seconds,
            }


class DistributedConsensusVerifier:
    """Verifies tool call results across multiple dispatch nodes.

    Uses quorum-based verification: a result is valid if at least
    N nodes (quorum) agree on the same result hash.
    """

    def __init__(self, quorum_size: int = _DEFAULT_QUORUM_SIZE):
        self.quorum_size = quorum_size
        self.proof_cache = ProofCache()

        # Track node results for consensus
        self.node_results: Dict[str, Dict[str, Any]] = {}  # node_id -> {proof_hash -> result}
        self._result_lock = threading.RLock()

        # Statistics
        self._stats = {
            'total_verifications': 0,
            'successful_verifications': 0,
            'failed_verifications': 0,
            'cached_hits': 0,
        }

    def hash_tool_result(self, tool_name: str, args: Dict[str, Any],
                        result: Any) -> str:
        """Create deterministic hash of tool result.

        Uses SHA-256 to create comparable hashes across nodes.
        Result must be JSON-serializable.
        """
        try:
            # Hash args and result together
            content = {
                'tool': tool_name,
                'args': args,
                'result': result,
            }

            json_str = json.dumps(content, sort_keys=True, default=str)
            return hashlib.sha256(json_str.encode()).hexdigest()
        except Exception as e:
            logger.warning(f"Failed to hash tool result: {e}")
            return hashlib.sha256(str(result).encode()).hexdigest()

    def verify_distributed(self, tool_name: str, args: Dict[str, Any],
                          node_results: Dict[str, Any],
                          require_all: bool = False) -> DistributedVerification:
        """Verify a tool call using distributed consensus.

        Args:
            tool_name: Name of the tool
            args: Arguments passed to the tool
            node_results: Dict of node_id -> result from that node
            require_all: If True, all nodes must agree; if False, just quorum

        Returns:
            DistributedVerification with consensus verdict
        """
        start_time = time.time()

        if not node_results:
            return DistributedVerification(
                is_verified=False,
                agreeing_nodes=[],
                disagreeing_nodes=[],
                quorum_size=self.quorum_size,
                verification_time_ms=0,
                error="No node results provided"
            )

        # Check proof cache first
        cache_key = hashlib.sha256(
            json.dumps(node_results, sort_keys=True, default=str).encode()
        ).hexdigest()

        cached = self.proof_cache.get(cache_key)
        if cached is not None:
            self._stats['cached_hits'] += 1
            verification_time_ms = (time.time() - start_time) * 1000

            return DistributedVerification(
                is_verified=cached,
                agreeing_nodes=list(node_results.keys()) if cached else [],
                disagreeing_nodes=[] if cached else list(node_results.keys()),
                quorum_size=self.quorum_size,
                verification_time_ms=verification_time_ms,
            )

        # Hash all results
        result_hashes: Dict[str, Set[str]] = {}  # hash -> {node_ids}

        for node_id, result in node_results.items():
            result_hash = self.hash_tool_result(tool_name, args, result)

            if result_hash not in result_hashes:
                result_hashes[result_hash] = set()

            result_hashes[result_hash].add(node_id)

        # Find consensus (most common result hash)
        consensus_hash = max(result_hashes.items(), key=lambda x: len(x[1]))[0]
        agreeing_nodes = list(result_hashes[consensus_hash])

        # Check if consensus meets quorum requirement
        if require_all:
            is_verified = len(agreeing_nodes) == len(node_results)
            disagreeing_nodes = [
                nid for nid in node_results.keys() if nid not in agreeing_nodes
            ]
        else:
            is_verified = len(agreeing_nodes) >= self.quorum_size
            disagreeing_nodes = [
                nid for nid in node_results.keys() if nid not in agreeing_nodes
            ]

        # Cache result
        self.proof_cache.store(cache_key, is_verified)

        # Update stats
        self._stats['total_verifications'] += 1
        if is_verified:
            self._stats['successful_verifications'] += 1
        else:
            self._stats['failed_verifications'] += 1

        verification_time_ms = (time.time() - start_time) * 1000

        return DistributedVerification(
            is_verified=is_verified,
            agreeing_nodes=agreeing_nodes,
            disagreeing_nodes=disagreeing_nodes,
            quorum_size=self.quorum_size,
            verification_time_ms=verification_time_ms,
        )

    def compare_results(self, results: List[Tuple[str, Any]]) -> Dict[str, Any]:
        """Compare results from multiple nodes.

        Args:
            results: List of (node_id, result) tuples

        Returns:
            Dict with comparison statistics
        """
        if not results:
            return {'comparison': 'no_results'}

        # Group by hash
        hash_groups: Dict[str, List[str]] = {}

        for node_id, result in results:
            result_hash = hashlib.sha256(
                json.dumps(result, sort_keys=True, default=str).encode()
            ).hexdigest()

            if result_hash not in hash_groups:
                hash_groups[result_hash] = []

            hash_groups[result_hash].append(node_id)

        # Sort by frequency
        sorted_groups = sorted(
            hash_groups.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )

        return {
            'total_nodes': len(results),
            'unique_results': len(hash_groups),
            'consensus_hash': sorted_groups[0][0] if sorted_groups else None,
            'consensus_nodes': sorted_groups[0][1] if sorted_groups else [],
            'all_agree': len(hash_groups) == 1,
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get verification statistics."""
        return {
            **self._stats,
            'proof_cache': self.proof_cache.get_stats(),
        }


# Global distributed verifier instance
_global_verifier: Optional[DistributedConsensusVerifier] = None
_verifier_lock = threading.Lock()


def get_distributed_verifier() -> DistributedConsensusVerifier:
    """Get or create global distributed verifier."""
    global _global_verifier

    if _global_verifier is None:
        with _verifier_lock:
            if _global_verifier is None:
                _global_verifier = DistributedConsensusVerifier()

    return _global_verifier


def verify_tool_call_distributed(tool_name: str, args: Dict[str, Any],
                                node_results: Dict[str, Any]) -> DistributedVerification:
    """Verify a distributed tool call."""
    verifier = get_distributed_verifier()
    return verifier.verify_distributed(tool_name, args, node_results)


def compare_tool_results(results: List[Tuple[str, Any]]) -> Dict[str, Any]:
    """Compare results from multiple nodes."""
    verifier = get_distributed_verifier()
    return verifier.compare_results(results)
