"""
JIT Profiler for Tool Call Acceleration (Phase 2)

Real-time tracking of tool call frequency and execution statistics to identify
hot paths (top 1% by call count) for JIT compilation.

Features:
  - Thread-safe call frequency tracking
  - Execution time sampling (windowed histogram)
  - Hot tool detection (top 1% threshold)
  - Incremental profile collection without periodic resets
  - Memory-efficient storage (circular buffers for timing samples)
"""

import json
import logging
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ToolExecutionStats:
    """Per-tool execution statistics."""
    name: str
    call_count: int = 0
    total_time_ms: float = 0.0
    min_time_ms: float = float('inf')
    max_time_ms: float = 0.0
    error_count: int = 0
    last_call_time: float = 0.0
    # Keep 100 most recent call times for distribution analysis
    recent_times: deque = field(default_factory=lambda: deque(maxlen=100))

    @property
    def avg_time_ms(self) -> float:
        """Average execution time in milliseconds."""
        return self.total_time_ms / max(1, self.call_count)

    @property
    def success_rate(self) -> float:
        """Percentage of successful calls (0-1)."""
        if self.call_count == 0:
            return 1.0
        return 1.0 - (self.error_count / self.call_count)

    def is_hot(self, total_calls: int, percentile: float = 0.99) -> bool:
        """Check if tool is in the hot zone (top 1% by frequency)."""
        if total_calls == 0:
            return False
        threshold = int(total_calls * (1.0 - percentile))
        return self.call_count >= threshold

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "name": self.name,
            "call_count": self.call_count,
            "total_time_ms": self.total_time_ms,
            "avg_time_ms": self.avg_time_ms,
            "min_time_ms": self.min_time_ms if self.min_time_ms != float('inf') else -1,
            "max_time_ms": self.max_time_ms,
            "error_count": self.error_count,
            "success_rate": self.success_rate,
            "last_call_time": self.last_call_time,
        }


class JITProfiler:
    """Thread-safe tool call profiler for identifying hot paths."""

    def __init__(self, max_history: int = 10000):
        """
        Initialize the profiler.

        Args:
            max_history: Maximum number of per-tool timing samples to retain
        """
        self.max_history = max_history
        self.stats: Dict[str, ToolExecutionStats] = {}
        self._lock = threading.RLock()
        self.total_calls = 0
        self.start_time = time.time()
        self.last_report_time = time.time()
        self._compilation_hints: Dict[str, dict] = {}

    def record_call(
        self,
        tool_name: str,
        duration_ms: float,
        success: bool = True,
        error_type: Optional[str] = None,
    ) -> None:
        """
        Record a tool execution.

        Args:
            tool_name: Name of the tool executed
            duration_ms: Execution time in milliseconds
            success: Whether the call succeeded
            error_type: Type of error if failed (for categorization)
        """
        with self._lock:
            if tool_name not in self.stats:
                self.stats[tool_name] = ToolExecutionStats(name=tool_name)

            stats = self.stats[tool_name]
            stats.call_count += 1
            stats.total_time_ms += duration_ms
            stats.min_time_ms = min(stats.min_time_ms, duration_ms)
            stats.max_time_ms = max(stats.max_time_ms, duration_ms)
            stats.last_call_time = time.time()
            stats.recent_times.append(duration_ms)

            if not success:
                stats.error_count += 1

            self.total_calls += 1

    def get_hot_tools(self, percentile: float = 0.99) -> List[Tuple[str, ToolExecutionStats]]:
        """
        Get tools in the hot zone (top 1% by frequency).

        Args:
            percentile: Include tools above this percentile (default 99th = top 1%)

        Returns:
            List of (tool_name, stats) sorted by call count descending
        """
        with self._lock:
            hot = [
                (name, stats)
                for name, stats in self.stats.items()
                if stats.is_hot(self.total_calls, percentile)
            ]
        return sorted(hot, key=lambda x: x[1].call_count, reverse=True)

    def get_stats(self, tool_name: str) -> Optional[ToolExecutionStats]:
        """Get statistics for a specific tool."""
        with self._lock:
            return self.stats.get(tool_name)

    def get_all_stats(self) -> Dict[str, ToolExecutionStats]:
        """Get a copy of all statistics."""
        with self._lock:
            return dict(self.stats)

    def get_profile_summary(self) -> dict:
        """Get a high-level profile summary."""
        with self._lock:
            elapsed = time.time() - self.start_time
            hot_tools = self.get_hot_tools()

            return {
                "timestamp": datetime.now().isoformat(),
                "elapsed_seconds": elapsed,
                "total_tool_calls": self.total_calls,
                "unique_tools": len(self.stats),
                "calls_per_second": self.total_calls / max(1, elapsed),
                "hot_tools_count": len(hot_tools),
                "hot_tools": [
                    {
                        "name": name,
                        "call_count": stats.call_count,
                        "avg_time_ms": stats.avg_time_ms,
                        "error_rate": 1.0 - stats.success_rate,
                    }
                    for name, stats in hot_tools
                ],
            }

    def save_profile(self, path: Path) -> None:
        """Save profile to a JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        summary = self.get_profile_summary()

        with self._lock:
            all_stats = {
                name: stats.to_dict() for name, stats in self.stats.items()
            }

        output = {
            "summary": summary,
            "tools": all_stats,
        }

        path.write_text(json.dumps(output, indent=2), encoding="utf-8")
        logger.info(f"Profile saved to {path}")

    def suggest_compilation_targets(self, min_call_count: int = 10) -> List[str]:
        """
        Suggest tools for JIT compilation based on frequency and performance.

        Args:
            min_call_count: Minimum calls to consider (avoids rare edge cases)

        Returns:
            List of tool names recommended for JIT compilation
        """
        hot_tools = self.get_hot_tools()
        candidates = []

        for name, stats in hot_tools:
            if stats.call_count >= min_call_count:
                # Prioritize high-frequency, high-latency tools for compilation
                # as compilation overhead becomes negligible at high volume
                candidates.append(name)

        return candidates

    def reset(self) -> None:
        """Clear all statistics (for testing or periodic resets)."""
        with self._lock:
            self.stats.clear()
            self.total_calls = 0
            self.start_time = time.time()

    def record_compilation_hint(
        self,
        tool_name: str,
        optimization_info: dict,
    ) -> None:
        """
        Record metadata about compilation for a tool.

        Args:
            tool_name: Name of the tool
            optimization_info: Dict with compilation details
        """
        with self._lock:
            self._compilation_hints[tool_name] = optimization_info


# Global profiler instance
_global_profiler: Optional[JITProfiler] = None
_profiler_lock = threading.Lock()


def get_global_profiler() -> JITProfiler:
    """Get or create the global profiler instance."""
    global _global_profiler
    if _global_profiler is None:
        with _profiler_lock:
            if _global_profiler is None:
                _global_profiler = JITProfiler()
    return _global_profiler


def profile_tool_call(tool_name: str, duration_ms: float, success: bool = True):
    """Record a tool call in the global profiler."""
    profiler = get_global_profiler()
    profiler.record_call(tool_name, duration_ms, success)


def is_tool_hot(tool_name: str, percentile: float = 0.99) -> bool:
    """Check if a tool is in the hot zone."""
    profiler = get_global_profiler()
    stats = profiler.get_stats(tool_name)
    if stats is None:
        return False
    return stats.is_hot(profiler.total_calls, percentile)


def get_hot_tools_list() -> List[str]:
    """Get list of hot tool names."""
    profiler = get_global_profiler()
    return [name for name, _ in profiler.get_hot_tools()]
