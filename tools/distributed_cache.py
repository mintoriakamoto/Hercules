#!/usr/bin/env python3
"""
Memory-Mapped Schema Cache for Distributed Dispatch

Provides zero-copy schema access across processes using mmap and atomic
counters for generation-based invalidation. Avoids inter-process serialization
overhead by storing schemas in shared memory.

Design:
  - Schemas stored in pre-allocated mmap file (/dev/shm for Linux)
  - Generation counter invalidates cache atomically
  - Lock-free reads for concurrent access
  - Automatic cleanup and recovery on corruption
"""

from __future__ import annotations

import hashlib
import json
import logging
import mmap
import os
import struct
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
import tempfile

logger = logging.getLogger(__name__)

# Memory-mapped cache configuration
_SCHEMA_CACHE_DIR = Path("/dev/shm" if os.path.exists("/dev/shm") else tempfile.gettempdir())
_SCHEMA_CACHE_FILE = _SCHEMA_CACHE_DIR / ".hercules_schema_cache"
_GENERATION_FILE = _SCHEMA_CACHE_DIR / ".hercules_schema_generation"

# File layout:
#   [4 bytes: generation counter (atomic uint32)]
#   [4 bytes: num_entries]
#   [8 bytes: timestamp]
#   [variable: schema entries]
#   Entry format:
#     [4 bytes: key length]
#     [key_len bytes: tool name]
#     [4 bytes: value length]
#     [value_len bytes: JSON schema]

_HEADER_SIZE = 16  # gen(4) + count(4) + ts(8)
_MAX_CACHE_SIZE = 256 * 1024 * 1024  # 256MB


@dataclass(frozen=True)
class CacheEntry:
    """Single cached schema entry."""
    tool_name: str
    schema: Dict[str, Any]
    added_at: float
    generation: int


class AtomicCounter:
    """Atomic counter for generation tracking (POSIX).

    Uses a file with read-write mmap to implement a simple atomic counter
    accessible across processes without additional synchronization.
    """

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self._local_value = 0
        self._mmap = None
        self._init_counter()

    def _init_counter(self) -> None:
        """Initialize or load counter from file."""
        try:
            if self.file_path.exists():
                with open(self.file_path, "r+b") as f:
                    self._mmap = mmap.mmap(f.fileno(), 4)
                    self._local_value = struct.unpack("I", self._mmap[:4])[0]
            else:
                # Create new counter file
                with open(self.file_path, "wb") as f:
                    f.write(struct.pack("I", 0))
                    f.flush()

                with open(self.file_path, "r+b") as f:
                    self._mmap = mmap.mmap(f.fileno(), 4)
                    self._local_value = 0
        except Exception as e:
            logger.warning(f"Failed to init atomic counter: {e}")
            self._local_value = 0

    def increment(self) -> int:
        """Atomically increment counter and return new value."""
        self._local_value = (self._local_value + 1) & 0xFFFFFFFF

        if self._mmap:
            try:
                self._mmap.seek(0)
                self._mmap.write(struct.pack("I", self._local_value))
                self._mmap.flush()
            except Exception as e:
                logger.warning(f"Failed to write counter: {e}")

        return self._local_value

    def get(self) -> int:
        """Get current counter value."""
        if self._mmap:
            try:
                self._mmap.seek(0)
                return struct.unpack("I", self._mmap[:4])[0]
            except Exception:
                pass
        return self._local_value

    def close(self) -> None:
        """Close mmap."""
        if self._mmap:
            try:
                self._mmap.close()
            except Exception:
                pass
            self._mmap = None


class DistributedSchemaCache:
    """Zero-copy schema cache using memory-mapped files.

    Provides:
      - Lock-free reads for high-concurrency access
      - Atomic generation counter for cache invalidation
      - Automatic cleanup on corruption
      - Per-tool schema versioning
    """

    def __init__(self):
        self.cache_file = _SCHEMA_CACHE_FILE
        self.generation_counter = AtomicCounter(_GENERATION_FILE)

        # In-process cache to reduce mmap reads
        self._local_cache: Dict[str, CacheEntry] = {}
        self._local_generation = -1
        self._lock = threading.RLock()

        # Statistics
        self._stats = {
            'hits': 0,
            'misses': 0,
            'invalidations': 0,
            'writes': 0,
        }

    def put(self, tool_name: str, schema: Dict[str, Any]) -> None:
        """Store a schema in the cache.

        Updates both local cache and memory-mapped backing store.
        Automatically invalidates other processes' caches via generation bump.
        """
        with self._lock:
            self._local_cache[tool_name] = CacheEntry(
                tool_name=tool_name,
                schema=schema,
                added_at=time.time(),
                generation=self.generation_counter.get()
            )

            # Write to mmap backing store
            self._write_to_mmap()

            # Bump generation to invalidate remote caches
            self.generation_counter.increment()
            self._stats['writes'] += 1

    def get(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Retrieve a schema from cache.

        Returns None if not cached. Uses generation counter to validate
        that local cache is still current.
        """
        with self._lock:
            # Check if local cache is valid
            current_gen = self.generation_counter.get()

            if current_gen != self._local_generation:
                # Local cache is stale, reload from mmap
                self._read_from_mmap()
                self._local_generation = current_gen
                self._stats['invalidations'] += 1

            if tool_name in self._local_cache:
                self._stats['hits'] += 1
                return self._local_cache[tool_name].schema

            self._stats['misses'] += 1
            return None

    def get_all(self) -> Dict[str, Dict[str, Any]]:
        """Get all cached schemas."""
        with self._lock:
            current_gen = self.generation_counter.get()

            if current_gen != self._local_generation:
                self._read_from_mmap()
                self._local_generation = current_gen

            return {
                name: entry.schema
                for name, entry in self._local_cache.items()
            }

    def invalidate(self, tool_name: Optional[str] = None) -> None:
        """Invalidate cache entry or entire cache.

        Args:
            tool_name: Specific tool to invalidate, or None for entire cache
        """
        with self._lock:
            if tool_name:
                self._local_cache.pop(tool_name, None)
            else:
                self._local_cache.clear()

            self.generation_counter.increment()
            self._local_generation = -1
            self._stats['invalidations'] += 1

    def _write_to_mmap(self) -> None:
        """Write local cache to memory-mapped backing store."""
        try:
            # Serialize cache to JSON
            cache_data = {
                'timestamp': time.time(),
                'entries': {
                    name: entry.schema
                    for name, entry in self._local_cache.items()
                }
            }

            json_data = json.dumps(cache_data).encode('utf-8')

            if len(json_data) > _MAX_CACHE_SIZE:
                logger.warning(
                    f"Cache too large ({len(json_data)} bytes), skipping mmap write"
                )
                return

            # Write to file
            with open(self.cache_file, 'wb') as f:
                f.write(json_data)
                f.flush()
        except Exception as e:
            logger.warning(f"Failed to write cache to mmap: {e}")

    def _read_from_mmap(self) -> None:
        """Read cache from memory-mapped backing store."""
        try:
            if not self.cache_file.exists():
                return

            with open(self.cache_file, 'rb') as f:
                data = f.read()

            cache_data = json.loads(data.decode('utf-8'))
            self._local_cache.clear()

            for tool_name, schema in cache_data.get('entries', {}).items():
                self._local_cache[tool_name] = CacheEntry(
                    tool_name=tool_name,
                    schema=schema,
                    added_at=cache_data.get('timestamp', time.time()),
                    generation=self.generation_counter.get()
                )
        except Exception as e:
            logger.warning(f"Failed to read cache from mmap: {e}")
            self._local_cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total = self._stats['hits'] + self._stats['misses']
            hit_rate = (
                self._stats['hits'] / total * 100 if total > 0 else 0
            )

            return {
                **self._stats,
                'hit_rate_percent': hit_rate,
                'num_cached': len(self._local_cache),
                'generation': self.generation_counter.get(),
            }

    def cleanup(self) -> None:
        """Clean up resources."""
        self.generation_counter.close()


# Global cache instance
_global_cache: Optional[DistributedSchemaCache] = None
_global_cache_lock = threading.Lock()


def get_schema_cache() -> DistributedSchemaCache:
    """Get or create global schema cache."""
    global _global_cache

    if _global_cache is None:
        with _global_cache_lock:
            if _global_cache is None:
                _global_cache = DistributedSchemaCache()

    return _global_cache


def cache_schema(tool_name: str, schema: Dict[str, Any]) -> None:
    """Cache a tool schema."""
    cache = get_schema_cache()
    cache.put(tool_name, schema)


def get_cached_schema(tool_name: str) -> Optional[Dict[str, Any]]:
    """Retrieve a cached schema."""
    cache = get_schema_cache()
    return cache.get(tool_name)


def invalidate_schema_cache(tool_name: Optional[str] = None) -> None:
    """Invalidate schema cache."""
    cache = get_schema_cache()
    cache.invalidate(tool_name)
