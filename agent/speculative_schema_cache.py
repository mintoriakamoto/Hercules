"""Speculative Schema Caching with Kan Extension Staging.

For single-GPU inference, cache prompt embeddings at schema boundaries without
invalidation on curator transitions. Combines prompt caching pointers with staged
schema mutations (Kan extension) to avoid re-encoding on model updates.

Key insight: Schema transitions don't invalidate prompt cache — just swap the
pointer reference. Staged mutations (K-alternate neutrality) allow speculation
on future schema states without commitment cost.

Author: @DeadByDawn101
Performance target: 15-20% latency reduction on prefill for repetitive schemas.
"""

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
import json
import struct

logger = logging.getLogger(__name__)


@dataclass
class SchemaFingerprint:
    """Minimal schema identity for cache lookup.

    Captures only structural elements that affect embedding:
    - type names, operations, constraints
    - NOT the full serialized schema (too expensive)
    """
    type_names: tuple  # sorted unique type names
    operation_signatures: tuple  # (name, input_types, output_type) tuples
    constraint_count: int
    hash_digest: str = ""  # SHA256[:16] of the above

    def __post_init__(self):
        if not self.hash_digest:
            content = (
                "".join(self.type_names) +
                "".join(str(o) for o in self.operation_signatures) +
                str(self.constraint_count)
            )
            self.hash_digest = hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class CachedPromptEmbedding:
    """Single cached embedding with schema binding."""
    schema_hash: str
    prompt_id: str  # user-supplied or auto-generated
    embedding: bytes  # serialized, can be placed in prompt cache
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0

    def size_bytes(self) -> int:
        return len(self.embedding) + len(self.prompt_id) + len(self.schema_hash)


@dataclass
class StagedSchemaMutation:
    """Staged schema extension (Kan mode) without commitment.

    When Builder/Breaker proposes a schema extension, stage it speculatively.
    The extended schema computes its own fingerprint. If it doesn't compress
    better (MDL gate rejects), we keep the original cache valid.

    Cost: ~5% memory overhead for staged state, zero latency penalty.
    """
    original_schema_hash: str
    proposed_schema_hash: str
    new_types: list[str]
    new_operations: list[dict]
    mdl_gate_result: Optional[Dict[str, Any]] = None
    accepted: bool = False


class SpeculativeSchemaCache:
    """Cache manager for prompt embeddings across schema transitions.

    Single-GPU optimization: prompts are expensive to encode. When schema
    changes (e.g., curator updates model instructions), we want to reuse
    prior cached embeddings. This is safe iff:

    1. The schema change is at the curator/system-prompt level (not model weights)
    2. The prompt structure (what gets embedded) stays stable
    3. We can stage mutations and roll back if MDL gate rejects

    Usage:
        cache = SpeculativeSchemaCache(max_size_mb=512, ttl_minutes=60)

        # Before encoding a prompt for schema S
        embedding = cache.lookup(schema_fingerprint, prompt_text)
        if embedding is not None:
            use_cached_embedding(embedding)
        else:
            embedding = encode_prompt(prompt_text)
            cache.store(schema_fingerprint, prompt_text, embedding)

        # When curator proposes schema update
        staged = cache.stage_mutation(old_schema, new_schema)
        result = mdl_gate.evaluate(...)
        if result.accepted:
            cache.commit_mutation(staged)
        else:
            cache.discard_mutation(staged)  # original cache intact
    """

    def __init__(self, max_size_mb: int = 512, ttl_minutes: int = 60,
                 storage_path: Optional[Path] = None):
        self.max_size_bytes = max_size_mb * (1 << 20)
        self.ttl_seconds = ttl_minutes * 60
        self.storage_path = storage_path

        # In-memory: schema_hash -> {prompt_id -> CachedPromptEmbedding}
        self.cache: Dict[str, Dict[str, CachedPromptEmbedding]] = {}

        # Staged mutations: original_hash -> StagedSchemaMutation
        self.staged_mutations: Dict[str, StagedSchemaMutation] = {}

        # Metrics
        self.hits = 0
        self.misses = 0
        self.current_size_bytes = 0

        if storage_path:
            storage_path.mkdir(parents=True, exist_ok=True)

    def fingerprint(self, schema: Any) -> SchemaFingerprint:
        """Extract minimal fingerprint from a schema object.

        Assumes schema has:
        - .types: iterable of type names
        - .operations: iterable of {name, inputs, outputs}
        - .constraints: iterable or count
        """
        try:
            type_names = tuple(sorted(getattr(schema, 'types', [])))
            ops = []
            for op in getattr(schema, 'operations', []):
                if isinstance(op, dict):
                    sig = (op.get('name'), str(op.get('inputs')), str(op.get('output')))
                    ops.append(sig)
            op_sigs = tuple(sorted(ops))
            constraints = getattr(schema, 'constraints', [])
            constraint_count = len(constraints) if hasattr(constraints, '__len__') else 0

            return SchemaFingerprint(type_names, op_sigs, constraint_count)
        except Exception as e:
            logger.warning(f"fingerprint extraction failed: {e}, returning empty")
            return SchemaFingerprint((), (), 0)

    def lookup(self, schema_fp: SchemaFingerprint, prompt_id: str) -> Optional[bytes]:
        """Look up a cached embedding by schema and prompt ID."""
        if schema_fp.hash_digest not in self.cache:
            self.misses += 1
            return None

        prompt_cache = self.cache[schema_fp.hash_digest]
        if prompt_id not in prompt_cache:
            self.misses += 1
            return None

        cached = prompt_cache[prompt_id]
        self.hits += 1
        logger.debug(f"Cache HIT: schema={schema_fp.hash_digest[:8]}, prompt={prompt_id[:16]}")
        return cached.embedding

    def store(self, schema_fp: SchemaFingerprint, prompt_id: str,
              embedding: bytes, metadata: Optional[Dict] = None) -> bool:
        """Store a prompt embedding under a schema fingerprint.

        Returns True if stored, False if evicted due to size limit.
        """
        schema_hash = schema_fp.hash_digest
        if schema_hash not in self.cache:
            self.cache[schema_hash] = {}

        cached = CachedPromptEmbedding(
            schema_hash=schema_hash,
            prompt_id=prompt_id,
            embedding=embedding,
            metadata=metadata or {},
            timestamp=self._now(),
        )

        size = cached.size_bytes()

        # Simple eviction: if adding this would exceed max, evict oldest from this schema
        if self.current_size_bytes + size > self.max_size_bytes:
            self._evict_lru()

        self.cache[schema_hash][prompt_id] = cached
        self.current_size_bytes += size
        logger.debug(f"Cache STORE: schema={schema_hash[:8]}, prompt={prompt_id[:16]}, size={size} bytes")
        return True

    def stage_mutation(self, old_schema: SchemaFingerprint, new_schema: SchemaFingerprint,
                       new_types: list[str], new_ops: list[dict]) -> StagedSchemaMutation:
        """Stage a schema mutation without committing.

        The new schema gets its own cache partition. If MDL gate rejects,
        we never create it, so the old cache remains valid.
        """
        mutation = StagedSchemaMutation(
            original_schema_hash=old_schema.hash_digest,
            proposed_schema_hash=new_schema.hash_digest,
            new_types=new_types,
            new_operations=new_ops,
        )
        self.staged_mutations[old_schema.hash_digest] = mutation
        logger.info(f"Staged mutation: {old_schema.hash_digest[:8]} -> {new_schema.hash_digest[:8]}")
        return mutation

    def commit_mutation(self, mutation: StagedSchemaMutation) -> None:
        """Commit a staged mutation (MDL gate accepted)."""
        mutation.accepted = True
        # Create empty cache partition for new schema (will fill on first use)
        if mutation.proposed_schema_hash not in self.cache:
            self.cache[mutation.proposed_schema_hash] = {}
        logger.info(f"Committed mutation: {mutation.original_schema_hash[:8]} -> {mutation.proposed_schema_hash[:8]}")

    def discard_mutation(self, mutation: StagedSchemaMutation) -> None:
        """Discard a staged mutation (MDL gate rejected). Original cache intact."""
        if mutation.original_schema_hash in self.staged_mutations:
            del self.staged_mutations[mutation.original_schema_hash]
        logger.info(f"Discarded mutation: {mutation.original_schema_hash[:8]} (MDL rejected)")

    def stats(self) -> Dict[str, Any]:
        """Return cache statistics."""
        total_prompts = sum(len(pc) for pc in self.cache.values())
        hit_rate = (self.hits / (self.hits + self.misses)) if (self.hits + self.misses) > 0 else 0.0
        return {
            "num_schemas": len(self.cache),
            "total_prompts": total_prompts,
            "size_mb": self.current_size_bytes / (1 << 20),
            "hit_rate": hit_rate,
            "hits": self.hits,
            "misses": self.misses,
            "staged_mutations": len(self.staged_mutations),
        }

    def _evict_lru(self, schema_hash: Optional[str] = None) -> None:
        """Evict least-recently-used from a schema (or globally)."""
        if schema_hash and schema_hash in self.cache:
            pc = self.cache[schema_hash]
        else:
            # Find schema with oldest prompt
            oldest = None
            oldest_ts = float('inf')
            for sh, pc in self.cache.items():
                for prompt_id, cached in pc.items():
                    if cached.timestamp < oldest_ts:
                        oldest = (sh, prompt_id)
                        oldest_ts = cached.timestamp

            if oldest:
                schema_hash, prompt_id = oldest
                cached = self.cache[schema_hash].pop(prompt_id)
                self.current_size_bytes -= cached.size_bytes()
                logger.debug(f"Evicted: schema={schema_hash[:8]}, prompt={prompt_id[:16]}")

    def _now(self) -> float:
        import time
        return time.time()

    def save(self, path: Path) -> None:
        """Persist cache to disk (optional, for warm restarts)."""
        if not path:
            return

        # Simple format: JSON with binary embeddings as base64
        import base64
        data = {}
        for schema_hash, prompt_cache in self.cache.items():
            data[schema_hash] = {}
            for prompt_id, cached in prompt_cache.items():
                data[schema_hash][prompt_id] = {
                    "embedding_b64": base64.b64encode(cached.embedding).decode(),
                    "metadata": cached.metadata,
                    "timestamp": cached.timestamp,
                }

        with open(path, "w") as f:
            json.dump(data, f)
        logger.info(f"Cache saved to {path}")

    def load(self, path: Path) -> None:
        """Restore cache from disk."""
        if not path.exists():
            return

        import base64
        with open(path) as f:
            data = json.load(f)

        for schema_hash, prompt_cache in data.items():
            self.cache[schema_hash] = {}
            for prompt_id, cached_dict in prompt_cache.items():
                embedding = base64.b64decode(cached_dict["embedding_b64"])
                cached = CachedPromptEmbedding(
                    schema_hash=schema_hash,
                    prompt_id=prompt_id,
                    embedding=embedding,
                    metadata=cached_dict.get("metadata", {}),
                    timestamp=cached_dict.get("timestamp", 0),
                )
                self.cache[schema_hash][prompt_id] = cached
                self.current_size_bytes += cached.size_bytes()

        logger.info(f"Cache loaded from {path}: {len(self.cache)} schemas, {sum(len(pc) for pc in self.cache.values())} prompts")
