"""Advanced context management and optimization.

Implements:
- Sliding window with relevance scoring
- Caching of expensive computations
- Automatic context prioritization
- Memory-efficient storage
"""

from typing import List, Dict, Any, Optional
import json
from dataclasses import dataclass
from collections import OrderedDict
import hashlib


@dataclass
class ContextItem:
    """Single context item with metadata."""
    content: str
    type: str  # "code", "error", "output", "plan", "thought"
    relevance: float = 1.0
    size_tokens: int = 0
    metadata: Dict[str, Any] = None
    timestamp: float = 0.0

    def compute_hash(self) -> str:
        """Compute content hash."""
        return hashlib.sha256(self.content.encode()).hexdigest()[:12]


class ContextWindow:
    """Intelligent context window management."""

    def __init__(
        self,
        max_tokens: int = 4000,
        reserve_tokens: int = 1000,
        window_strategy: str = "sliding_relevance"
    ):
        """Initialize context window.

        Args:
            max_tokens: Maximum tokens in window
            reserve_tokens: Tokens reserved for response
            window_strategy: "sliding_relevance", "recency", "importance"
        """
        self.max_tokens = max_tokens
        self.reserve_tokens = reserve_tokens
        self.available_tokens = max_tokens - reserve_tokens
        self.window_strategy = window_strategy
        self.items: OrderedDict[str, ContextItem] = OrderedDict()
        self.total_tokens = 0

    def add_item(self, content: str, item_type: str, **metadata) -> bool:
        """Add item to context.

        Returns:
            True if added, False if no room
        """
        item = ContextItem(
            content=content,
            type=item_type,
            metadata=metadata,
        )

        item_hash = item.compute_hash()
        item.size_tokens = self._estimate_tokens(content)

        if item_hash in self.items:
            return True  # Already present

        if self.total_tokens + item.size_tokens > self.available_tokens:
            # Make room
            self._evict_items(item.size_tokens)

        self.items[item_hash] = item
        self.total_tokens += item.size_tokens
        return True

    def _estimate_tokens(self, content: str) -> int:
        """Rough token estimation."""
        return max(1, len(content) // 4)

    def _evict_items(self, needed_tokens: int):
        """Evict lowest-relevance items."""
        while self.total_tokens + needed_tokens > self.available_tokens:
            if not self.items:
                break

            # Score items by strategy
            if self.window_strategy == "sliding_relevance":
                scores = {
                    k: v.relevance for k, v in self.items.items()
                }
            elif self.window_strategy == "recency":
                scores = {
                    k: v.timestamp for k, v in self.items.items()
                }
            elif self.window_strategy == "importance":
                scores = {
                    k: 1.0 if v.type in ["error", "plan"] else 0.5
                    for k, v in self.items.items()
                }
            else:
                scores = {k: 0.5 for k in self.items}

            # Evict lowest score
            worst_key = min(scores.items(), key=lambda x: x[1])[0]
            worst_item = self.items.pop(worst_key)
            self.total_tokens -= worst_item.size_tokens

    def update_relevance(self, item_hash: str, relevance: float):
        """Update item relevance score."""
        if item_hash in self.items:
            self.items[item_hash].relevance = max(0, min(1, relevance))

    def get_context(self) -> str:
        """Get formatted context for API."""
        sections = {}
        for item_hash, item in self.items.items():
            if item.type not in sections:
                sections[item.type] = []
            sections[item.type].append(item.content)

        context = []
        for section_type in ["code", "plan", "thought", "error", "output"]:
            if section_type in sections:
                context.append(f"### {section_type.upper()}\n")
                context.extend(sections[section_type])
                context.append("")

        return "\n".join(context)


class ContextCache:
    """Cache expensive context computations."""

    def __init__(self, max_cache_size: int = 100):
        self.cache: Dict[str, Any] = OrderedDict()
        self.max_size = max_cache_size

    def get(self, key: str) -> Optional[Any]:
        """Get cached value."""
        if key in self.cache:
            # Move to end (LRU)
            self.cache.move_to_end(key)
            return self.cache[key]
        return None

    def set(self, key: str, value: Any):
        """Set cached value."""
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value

        if len(self.cache) > self.max_size:
            # Remove oldest
            self.cache.popitem(last=False)

    def compute_cached(self, key: str, fn: callable, *args) -> Any:
        """Get or compute cached value."""
        cached = self.get(key)
        if cached is not None:
            return cached

        result = fn(*args)
        self.set(key, result)
        return result


__all__ = ["ContextWindow", "ContextItem", "ContextCache"]
