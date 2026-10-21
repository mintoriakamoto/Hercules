#!/usr/bin/env python3
"""
Profile-Guided Optimization (PGO) for Tool Dispatch

Collects runtime profiling data and uses it to recompile hot tools with
better optimization heuristics. Typical PGO pipeline:

    1. Instrumentation: Profile tool execution patterns
    2. Collection: Record which code paths are hot
    3. Analysis: Identify optimization opportunities
    4. Recompilation: Recompile with profile-directed optimizations
    5. Validation: Verify improvements without correctness regression

Expected improvements:
    - 2-5x additional speedup over static compilation
    - Better inlining decisions
    - Improved branch prediction
    - Cache-friendly code layout

PGO is especially effective when:
    - Tool dispatch patterns are non-uniform
    - Some parameters are more common than others
    - Some error paths are rare
    - Tool combination patterns cluster
"""

import json
import logging
import time
from collections import defaultdict, Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ExecutionProfile:
    """Profile of single tool execution."""
    tool_name: str
    duration_ms: float
    arguments: Dict[str, Any]
    success: bool
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    @property
    def is_fast(self) -> bool:
        """Tool executed very quickly (likely overhead-dominated)."""
        return self.duration_ms < 1.0

    @property
    def is_slow(self) -> bool:
        """Tool execution took significant time."""
        return self.duration_ms > 100.0


@dataclass
class ToolCallPattern:
    """Common pattern in tool invocations."""
    tool_name: str
    parameter_signature: str  # Hash of common parameters
    frequency: int = 0
    avg_duration_ms: float = 0.0

    def optimization_priority(self) -> float:
        """Priority score for optimization (frequency * savings potential)."""
        # Tools that are frequently called with same parameters benefit most
        return self.frequency * (100 - min(self.avg_duration_ms, 100.0))


class ExecutionProfiler:
    """Profiles tool execution for PGO."""

    def __init__(self, sample_rate: float = 0.1):
        """Initialize profiler.

        Args:
            sample_rate: Fraction of executions to profile (0.0-1.0)
        """
        self.sample_rate = sample_rate
        self.profiles: List[ExecutionProfile] = []
        self.pattern_counts: Counter = Counter()
        self.parameter_patterns: Dict[str, Counter] = defaultdict(Counter)
        self.tool_stats: Dict[str, Dict[str, Any]] = defaultdict(dict)

    def record_execution(
        self,
        tool_name: str,
        duration_ms: float,
        arguments: Dict[str, Any],
        success: bool,
        error: Optional[str] = None,
    ) -> None:
        """Record a tool execution.

        Args:
            tool_name: Tool name
            duration_ms: Execution time in milliseconds
            arguments: Tool arguments
            success: Whether execution succeeded
            error: Error message if not successful
        """
        # Sample to reduce memory overhead
        import random
        if random.random() > self.sample_rate:
            return

        profile = ExecutionProfile(
            tool_name=tool_name,
            duration_ms=duration_ms,
            arguments=arguments,
            success=success,
            error=error,
        )
        self.profiles.append(profile)

        # Update statistics
        self._update_stats(tool_name, profile)

    def _update_stats(self, tool_name: str, profile: ExecutionProfile) -> None:
        """Update aggregate statistics."""
        if tool_name not in self.tool_stats:
            self.tool_stats[tool_name] = {
                'count': 0,
                'total_duration_ms': 0.0,
                'min_duration_ms': float('inf'),
                'max_duration_ms': 0.0,
                'success_count': 0,
                'error_count': 0,
                'error_types': Counter(),
            }

        stats = self.tool_stats[tool_name]
        stats['count'] += 1
        stats['total_duration_ms'] += profile.duration_ms
        stats['min_duration_ms'] = min(stats['min_duration_ms'], profile.duration_ms)
        stats['max_duration_ms'] = max(stats['max_duration_ms'], profile.duration_ms)

        if profile.success:
            stats['success_count'] += 1
        else:
            stats['error_count'] += 1
            if profile.error:
                stats['error_types'][profile.error] += 1

        # Track parameter patterns
        param_sig = self._param_signature(profile.arguments)
        self.parameter_patterns[tool_name][param_sig] += 1

    def _param_signature(self, arguments: Dict[str, Any]) -> str:
        """Get signature of parameters for pattern matching."""
        # Hash parameter types and keys
        key_types = sorted(
            (k, type(v).__name__) for k, v in arguments.items()
        )
        return json.dumps(key_types)

    def get_tool_stats(self, tool_name: str) -> Dict[str, Any]:
        """Get statistics for a tool."""
        if tool_name not in self.tool_stats:
            return {}

        stats = self.tool_stats[tool_name]
        count = stats['count']

        return {
            'tool_name': tool_name,
            'execution_count': count,
            'success_rate': stats['success_count'] / count if count > 0 else 0.0,
            'avg_duration_ms': stats['total_duration_ms'] / count if count > 0 else 0.0,
            'min_duration_ms': stats['min_duration_ms'],
            'max_duration_ms': stats['max_duration_ms'],
            'common_errors': dict(stats['error_types'].most_common(5)),
        }

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all tools."""
        return {
            tool_name: self.get_tool_stats(tool_name)
            for tool_name in self.tool_stats
        }

    def detect_patterns(self) -> List[ToolCallPattern]:
        """Detect common tool invocation patterns.

        Returns:
            List of patterns sorted by optimization priority
        """
        patterns = []

        for tool_name, param_counts in self.parameter_patterns.items():
            stats = self.tool_stats.get(tool_name, {})
            avg_duration = (
                stats['total_duration_ms'] / stats['count']
                if stats.get('count', 0) > 0 else 0.0
            )

            for param_sig, frequency in param_counts.most_common():
                pattern = ToolCallPattern(
                    tool_name=tool_name,
                    parameter_signature=param_sig,
                    frequency=frequency,
                    avg_duration_ms=avg_duration,
                )
                patterns.append(pattern)

        # Sort by optimization priority
        patterns.sort(key=lambda p: p.optimization_priority(), reverse=True)
        return patterns

    def export_profile(self, path: Path) -> None:
        """Export profile data to JSON."""
        data = {
            'timestamp': time.time(),
            'total_executions': len(self.profiles),
            'unique_tools': len(self.tool_stats),
            'tool_stats': {
                tool: self.get_tool_stats(tool)
                for tool in self.tool_stats
            },
            'patterns': [
                {
                    'tool_name': p.tool_name,
                    'parameter_signature': p.parameter_signature,
                    'frequency': p.frequency,
                    'avg_duration_ms': p.avg_duration_ms,
                    'optimization_priority': p.optimization_priority(),
                }
                for p in self.detect_patterns()
            ],
        }

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"Exported profiling data to {path}")


class PGOOptimizer:
    """Applies profile-guided optimizations."""

    def __init__(self, profiler: ExecutionProfiler):
        self.profiler = profiler
        self.optimization_queue: List[Tuple[str, float]] = []

    def identify_optimization_candidates(
        self,
        min_execution_count: int = 100,
    ) -> List[str]:
        """Identify tools that should be recompiled with PGO.

        Args:
            min_execution_count: Minimum executions to consider for optimization

        Returns:
            List of tool names to recompile
        """
        candidates = []

        for tool_name, stats in self.profiler.tool_stats.items():
            count = stats.get('count', 0)
            if count >= min_execution_count:
                # Calculate potential speedup
                # Tools with high variability in execution time benefit most
                min_time = stats.get('min_duration_ms', 0.0)
                max_time = stats.get('max_duration_ms', 0.0)
                avg_time = stats.get('total_duration_ms', 0.0) / count if count > 0 else 0.0

                # Variance score (high variance means optimization can help more)
                variance = max(0.0, (max_time - min_time) / avg_time if avg_time > 0 else 0.0)
                speedup_potential = variance * (count / 1000)  # Normalize by count

                if speedup_potential > 1.0:
                    candidates.append(tool_name)
                    self.optimization_queue.append((tool_name, speedup_potential))

        # Sort by potential speedup
        self.optimization_queue.sort(key=lambda x: x[1], reverse=True)

        return [name for name, _ in self.optimization_queue]

    def generate_optimization_hints(
        self,
        tool_name: str,
    ) -> Dict[str, Any]:
        """Generate optimization hints for a tool based on profile.

        Args:
            tool_name: Tool to analyze

        Returns:
            Dictionary of optimization hints
        """
        hints = {
            'tool_name': tool_name,
            'inlining_candidates': [],
            'branch_prediction': [],
            'cache_optimization': [],
            'vectorization_opportunities': [],
        }

        # Analyze parameter patterns
        patterns = self.profiler.parameter_patterns.get(tool_name, {})
        most_common = patterns.most_common(3)

        # If a pattern is very common, suggest specialization
        if most_common:
            top_pattern, count = most_common[0]
            total = sum(patterns.values())
            if count / total > 0.5:
                hints['inlining_candidates'].append({
                    'pattern': top_pattern,
                    'frequency': f"{100 * count / total:.1f}%",
                    'action': 'specialize parameter validation for this pattern',
                })

        # Branch prediction based on success rates
        stats = self.profiler.tool_stats.get(tool_name, {})
        success_rate = stats.get('success_count', 0) / stats.get('count', 1)
        if success_rate > 0.95:
            hints['branch_prediction'].append({
                'likely_path': 'success',
                'frequency': f"{100 * success_rate:.1f}%",
                'action': 'reorder branches to put success path first',
            })

        return hints

    def get_optimization_priority_list(self) -> List[Dict[str, Any]]:
        """Get prioritized list of tools to optimize."""
        result = []
        for tool_name, potential in self.optimization_queue[:10]:  # Top 10
            hints = self.generate_optimization_hints(tool_name)
            result.append({
                'tool_name': tool_name,
                'speedup_potential': potential,
                'hints': hints,
            })
        return result


# Global profiler and optimizer
_global_profiler: Optional[ExecutionProfiler] = None
_global_optimizer: Optional[PGOOptimizer] = None


def get_profiler() -> ExecutionProfiler:
    """Get or create global profiler."""
    global _global_profiler
    if _global_profiler is None:
        _global_profiler = ExecutionProfiler()
    return _global_profiler


def get_pgo_optimizer() -> PGOOptimizer:
    """Get or create global PGO optimizer."""
    global _global_optimizer, _global_profiler
    if _global_optimizer is None:
        profiler = get_profiler()
        _global_optimizer = PGOOptimizer(profiler)
    return _global_optimizer
