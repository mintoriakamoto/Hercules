"""Unified compression strategy interface.

Consolidates trajectory_compressor, context_compressor, and auxiliary compression
into a single pluggable architecture with observable strategies and fallbacks.

This module provides:
  - CompressionStrategy: pluggable interface for different compression algorithms
  - StrategyFactory: creates configured strategies
  - Compressor: unified entry point for all compression needs
  - Metrics: per-strategy compression ratio tracking
"""

from __future__ import annotations

import abc
import hashlib
import json
import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CompressionLevel(Enum):
    """Compression strategy intensity levels."""
    NONE = "none"              # No compression
    CONSERVATIVE = "conservative"  # Minimal compression
    BALANCED = "balanced"      # Default balance of compression vs. quality
    AGGRESSIVE = "aggressive"  # Maximum compression
    CUSTOM = "custom"          # User-provided custom settings


@dataclass
class CompressionMetrics:
    """Metrics for a compression operation."""
    original_size: int
    compressed_size: int
    ratio: float  # compressed / original
    duration_ms: float
    strategy: str
    content_type: str  # "trajectory", "context", "summary", etc.

    @property
    def saved_bytes(self) -> int:
        """Bytes saved by compression."""
        return self.original_size - self.compressed_size

    @property
    def saved_percent(self) -> float:
        """Percentage of content removed."""
        if self.original_size == 0:
            return 0.0
        return (self.saved_bytes / self.original_size) * 100


class CompressionStrategy(abc.ABC):
    """Abstract base for compression strategies.

    Implementations handle different compression algorithms:
    - No compression (pass-through)
    - Summary-based (extract key points)
    - Token budget (trim to fit budget)
    - Hybrid (combination of strategies)
    """

    def __init__(self, name: str):
        self.name = name

    @abc.abstractmethod
    def compress(
        self,
        content: str,
        max_tokens: Optional[int] = None,
        content_type: str = "unknown",
    ) -> str:
        """Compress content to fit within constraints.

        Args:
            content: Text to compress
            max_tokens: Target token budget (None = no hard limit)
            content_type: Type of content (trajectory, context, summary, etc.)

        Returns:
            Compressed version of content

        Raises:
            CompressionError: If compression fails
        """
        pass

    def estimate_tokens(self, content: str) -> int:
        """Estimate token count for content.

        Default: char/4 heuristic. Override for better accuracy.
        """
        return max(1, len(content) // 4)


class NoCompression(CompressionStrategy):
    """Pass-through strategy: no compression applied."""

    def __init__(self):
        super().__init__("none")

    def compress(
        self,
        content: str,
        max_tokens: Optional[int] = None,
        content_type: str = "unknown",
    ) -> str:
        """Return content unchanged."""
        return content


class ConservativeCompression(CompressionStrategy):
    """Minimal compression: preserve most details, trim redundancy only."""

    def __init__(self):
        super().__init__("conservative")

    def compress(
        self,
        content: str,
        max_tokens: Optional[int] = None,
        content_type: str = "unknown",
    ) -> str:
        """Apply conservative compression (trim only redundancy)."""
        if not content or max_tokens is None:
            return content

        # Estimate current tokens
        current_tokens = self.estimate_tokens(content)
        if current_tokens <= max_tokens:
            return content

        # Conservative: trim to fit, preserve structure
        target_chars = max_tokens * 4
        if len(content) <= target_chars:
            return content

        # Graceful truncation with ellipsis
        truncated = content[:target_chars].rsplit(' ', 1)[0]
        return f"{truncated}...[truncated]"


class BalancedCompression(CompressionStrategy):
    """Default strategy: balance compression vs. content quality."""

    def __init__(self):
        super().__init__("balanced")

    def compress(
        self,
        content: str,
        max_tokens: Optional[int] = None,
        content_type: str = "unknown",
    ) -> str:
        """Apply balanced compression."""
        if not content or max_tokens is None:
            return content

        current_tokens = self.estimate_tokens(content)
        if current_tokens <= max_tokens:
            return content

        # Target 70% of max_tokens (leaves 30% buffer)
        target_tokens = int(max_tokens * 0.7)
        target_chars = target_tokens * 4

        if len(content) <= target_chars:
            return content

        # Try to break at logical boundary (paragraph, sentence)
        truncated = content[:target_chars]

        # Look for paragraph break
        last_break = truncated.rfind('\n\n')
        if last_break > target_chars * 0.8:
            return content[:last_break].strip()

        # Look for sentence break
        last_sentence = truncated.rfind('. ')
        if last_sentence > target_chars * 0.75:
            return content[:last_sentence + 1].strip()

        # Fallback: word boundary
        last_word = truncated.rsplit(' ', 1)[0]
        return f"{last_word}...[compressed]"


class AggressiveCompression(CompressionStrategy):
    """Maximum compression: summarize, drop details, fit hard budget."""

    def __init__(self):
        super().__init__("aggressive")

    def compress(
        self,
        content: str,
        max_tokens: Optional[int] = None,
        content_type: str = "unknown",
    ) -> str:
        """Apply aggressive compression."""
        if not content or max_tokens is None:
            return content

        current_tokens = self.estimate_tokens(content)
        if current_tokens <= max_tokens:
            return content

        # Target 50% of max_tokens (strict)
        target_tokens = int(max_tokens * 0.5)
        target_chars = target_tokens * 4

        # Extract key lines (first of each paragraph)
        lines = content.split('\n')
        key_lines = []
        current_size = 0

        for line in lines:
            if not line.strip():
                continue
            if current_size + len(line) <= target_chars:
                key_lines.append(line.strip())
                current_size += len(line)
            else:
                break

        if key_lines:
            return '\n'.join(key_lines) + '\n[...compressed significantly...]'

        # Fallback to hard truncation
        truncated = content[:target_chars]
        return f"{truncated}...[compressed]"


class StrategyFactory:
    """Factory for creating compression strategies."""

    _strategies: Dict[str, CompressionStrategy] = {}

    @classmethod
    def register_strategy(cls, strategy: CompressionStrategy) -> None:
        """Register a compression strategy."""
        cls._strategies[strategy.name] = strategy

    @classmethod
    def create(cls, level: str | CompressionLevel) -> CompressionStrategy:
        """Create a compression strategy by name or level.

        Args:
            level: Strategy name (string) or CompressionLevel enum

        Returns:
            CompressionStrategy instance

        Raises:
            ValueError: If strategy not found
        """
        if isinstance(level, CompressionLevel):
            level = level.value

        if level in cls._strategies:
            return cls._strategies[level]

        raise ValueError(f"Unknown compression strategy: {level}")

    @classmethod
    def available_strategies(cls) -> List[str]:
        """List all available strategy names."""
        return sorted(cls._strategies.keys())


# Register default strategies
StrategyFactory.register_strategy(NoCompression())
StrategyFactory.register_strategy(ConservativeCompression())
StrategyFactory.register_strategy(BalancedCompression())
StrategyFactory.register_strategy(AggressiveCompression())


class Compressor:
    """Unified compression interface.

    Provides single entry point for all compression needs with:
    - Strategy selection
    - Metrics collection
    - Backwards compatibility
    - Observable compression behavior
    """

    def __init__(
        self,
        strategy: str | CompressionLevel | CompressionStrategy = "balanced",
        enable_metrics: bool = True,
        fallback_to_truncate: bool = True,
    ):
        """Initialize compressor.

        Args:
            strategy: Compression strategy to use
            enable_metrics: Collect compression metrics
            fallback_to_truncate: Truncate if strategy fails
        """
        if isinstance(strategy, CompressionStrategy):
            self.strategy = strategy
        else:
            self.strategy = StrategyFactory.create(strategy)

        self.enable_metrics = enable_metrics
        self.fallback_to_truncate = fallback_to_truncate
        self.metrics_log: List[CompressionMetrics] = []

    def compress(
        self,
        content: str,
        max_tokens: Optional[int] = None,
        content_type: str = "unknown",
    ) -> str:
        """Compress content with metrics collection.

        Args:
            content: Text to compress
            max_tokens: Target token budget
            content_type: Type of content (for metrics)

        Returns:
            Compressed content
        """
        import time
        start_time = time.time()
        original_size = len(content)

        try:
            compressed = self.strategy.compress(
                content,
                max_tokens=max_tokens,
                content_type=content_type,
            )
        except Exception as e:
            logger.error(
                "Compression failed with %s: %s",
                self.strategy.name,
                str(e),
            )
            if self.fallback_to_truncate and max_tokens:
                # Fallback: hard truncation
                target_chars = max_tokens * 4
                compressed = f"{content[:target_chars]}...[truncated]"
            else:
                compressed = content

        # Collect metrics
        if self.enable_metrics:
            duration_ms = (time.time() - start_time) * 1000
            compressed_size = len(compressed)
            ratio = compressed_size / original_size if original_size > 0 else 0.0

            metrics = CompressionMetrics(
                original_size=original_size,
                compressed_size=compressed_size,
                ratio=ratio,
                duration_ms=duration_ms,
                strategy=self.strategy.name,
                content_type=content_type,
            )
            self.metrics_log.append(metrics)

            # Log compression result
            if ratio < 1.0:
                logger.debug(
                    "Compressed %s: %d → %d bytes (%.1f%% reduction, %.2fms)",
                    content_type,
                    original_size,
                    compressed_size,
                    (1.0 - ratio) * 100,
                    duration_ms,
                )

        return compressed

    def get_metrics(self) -> List[CompressionMetrics]:
        """Get collected compression metrics."""
        return self.metrics_log.copy()

    def clear_metrics(self) -> None:
        """Clear metrics log."""
        self.metrics_log.clear()


# Backwards compatibility: module-level factory
_default_compressor: Optional[Compressor] = None


def get_default_compressor(level: str = "balanced") -> Compressor:
    """Get or create global compressor instance.

    This maintains backwards compatibility with existing code
    that doesn't explicitly create a compressor.
    """
    global _default_compressor
    if _default_compressor is None:
        _default_compressor = Compressor(strategy=level)
    return _default_compressor


def set_default_compressor(compressor: Compressor) -> None:
    """Set global compressor instance."""
    global _default_compressor
    _default_compressor = compressor
