#!/usr/bin/env python3
"""Integration layer for system-level optimizations.

Hooks NUMA awareness, CPU affinity, memory pooling, cache optimization,
power management, and syscall reduction into the tool execution pipeline.

Provides a unified interface for enabling/disabling optimizations via
environment variables and configuration.
"""

import json
import logging
import os
import threading
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class SystemOptimizationConfig:
    """Configuration for all system-level optimizations."""

    def __init__(self):
        self.enabled = os.getenv("SYSTEM_OPTIMIZATIONS_ENABLED", "true").lower() == "true"

        # Individual optimization flags
        self.numa_aware = os.getenv("NUMA_DISPATCH_ENABLED", "false").lower() == "true"
        self.cpu_affinity = os.getenv("CPU_AFFINITY_ENABLED", "false").lower() == "true"
        self.memory_pooling = os.getenv("MEMORY_POOLING_ENABLED", "true").lower() == "true"
        self.cache_optimize = os.getenv("CACHE_OPTIMIZER_ENABLED", "false").lower() == "true"
        self.power_optimize = os.getenv("POWER_OPTIMIZER_ENABLED", "false").lower() == "true"
        self.syscall_reduce = os.getenv("SYSCALL_REDUCE_ENABLED", "false").lower() == "true"

        # Advanced flags
        self.profile_enabled = os.getenv("SYSTEM_PROFILE_ENABLED", "false").lower() == "true"
        self.verbose_logging = os.getenv("SYSTEM_OPT_VERBOSE", "false").lower() == "true"

    def is_any_enabled(self) -> bool:
        """Check if any optimization is enabled."""
        return any([
            self.numa_aware,
            self.cpu_affinity,
            self.memory_pooling,
            self.cache_optimize,
            self.power_optimize,
            self.syscall_reduce,
        ])

    def to_dict(self) -> Dict[str, bool]:
        """Export as dictionary."""
        return {
            "enabled": self.enabled,
            "numa_aware": self.numa_aware,
            "cpu_affinity": self.cpu_affinity,
            "memory_pooling": self.memory_pooling,
            "cache_optimize": self.cache_optimize,
            "power_optimize": self.power_optimize,
            "syscall_reduce": self.syscall_reduce,
            "profile_enabled": self.profile_enabled,
        }


class ToolOptimizationContext:
    """Context for executing a single tool with optimizations."""

    def __init__(self, tool_name: str, args: Dict[str, Any]):
        self.tool_name = tool_name
        self.args = args
        self.start_time = 0.0
        self.numa_node = -1
        self.cpu_cores = []
        self.arg_buffer = None
        self.result_buffer = None

    def __enter__(self):
        """Enter optimization context."""
        import time

        self.start_time = time.perf_counter()

        if not _config.enabled:
            return self

        # NUMA awareness
        if _config.numa_aware:
            self._setup_numa()

        # CPU affinity
        if _config.cpu_affinity:
            self._setup_cpu_affinity()

        # Memory pooling
        if _config.memory_pooling:
            self._setup_memory_pool()

        # Cache optimization
        if _config.cache_optimize:
            self._setup_cache_optimization()

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit optimization context."""
        if not _config.enabled:
            return

        # Cleanup
        if self.arg_buffer:
            try:
                from tools.memory_pool import release_arg_buffer

                release_arg_buffer(self.arg_buffer)
            except Exception:
                pass

        if self.result_buffer:
            try:
                from tools.memory_pool import release_result_buffer

                release_result_buffer(self.result_buffer)
            except Exception:
                pass

    def _setup_numa(self) -> None:
        """Setup NUMA affinity."""
        try:
            from tools.numa_aware_dispatch import dispatch_tool_numa

            # Note: actual dispatch happens in with_optimized_execution
            self.numa_node = 0  # Placeholder
        except Exception as e:
            logger.debug("NUMA setup failed: %s", e)

    def _setup_cpu_affinity(self) -> None:
        """Setup CPU affinity."""
        try:
            from tools.cpu_affinity_scheduler import schedule_tool_affinity

            self.cpu_cores = schedule_tool_affinity(self.tool_name) or []
        except Exception as e:
            logger.debug("CPU affinity setup failed: %s", e)

    def _setup_memory_pool(self) -> None:
        """Setup memory pooling."""
        try:
            from tools.memory_pool import acquire_arg_buffer

            self.arg_buffer = acquire_arg_buffer(self.args)
        except Exception as e:
            logger.debug("Memory pool setup failed: %s", e)

    def _setup_cache_optimization(self) -> None:
        """Setup cache optimization."""
        try:
            from tools.cache_optimizer import optimize_tool_schema

            # Pre-optimize schema if available
            pass
        except Exception as e:
            logger.debug("Cache optimization setup failed: %s", e)

    def get_elapsed_ms(self) -> float:
        """Get elapsed time since context entry."""
        import time

        return (time.perf_counter() - self.start_time) * 1000.0


class SystemOptimizationManager:
    """Central manager for system-level optimizations."""

    def __init__(self):
        self.config = SystemOptimizationConfig()
        self.contexts: Dict[int, ToolOptimizationContext] = {}
        self._contexts_lock = threading.Lock()
        self._initialized = False

        if self.config.enabled and self.config.is_any_enabled():
            self._initialize()

    def _initialize(self) -> None:
        """Initialize optimization subsystems."""
        try:
            if self.config.memory_pooling:
                from tools.memory_pool import initialize_pools

                initialize_pools()
                logger.debug("Memory pooling initialized")

            if self.config.power_optimize:
                from tools.power_optimizer import initialize_power_optimizer

                initialize_power_optimizer()
                logger.debug("Power optimizer initialized")

            self._initialized = True
        except Exception as e:
            logger.warning("Optimization initialization failed: %s", e)

    def create_context(
        self,
        tool_name: str,
        args: Dict[str, Any],
    ) -> ToolOptimizationContext:
        """Create optimization context for a tool call."""
        if not self.config.enabled:
            # Return no-op context
            return ToolOptimizationContext(tool_name, args)

        context = ToolOptimizationContext(tool_name, args)
        context_id = id(context)

        with self._contexts_lock:
            self.contexts[context_id] = context

        return context

    def with_optimized_execution(
        self,
        tool_name: str,
        args: Dict[str, Any],
        execute_fn: Callable[[], Any],
    ) -> Any:
        """Execute tool with system-level optimizations."""
        if not self.config.enabled or not self.config.is_any_enabled():
            return execute_fn()

        with self.create_context(tool_name, args) as ctx:
            try:
                # NUMA-aware execution
                if self.config.numa_aware:
                    try:
                        from tools.numa_aware_dispatch import dispatch_tool_numa

                        return dispatch_tool_numa(tool_name, args, execute_fn)
                    except Exception as e:
                        logger.debug("NUMA dispatch failed: %s", e)

                # Standard execution with other optimizations active
                return execute_fn()

            except Exception as e:
                logger.warning("Optimized execution failed: %s", e)
                # Fallback to standard execution
                return execute_fn()

    def get_metrics(self) -> Dict[str, Any]:
        """Get metrics from all active optimizations."""
        metrics = {}

        if self.config.memory_pooling:
            try:
                from tools.memory_pool import get_pool_stats

                metrics["memory_pool"] = get_pool_stats()
            except Exception:
                pass

        if self.config.power_optimize:
            try:
                from tools.power_optimizer import get_power_metrics

                metrics["power"] = get_power_metrics()
            except Exception:
                pass

        if self.config.syscall_reduce:
            try:
                from tools.syscall_reducer import get_syscall_metrics

                metrics["syscalls"] = get_syscall_metrics()
            except Exception:
                pass

        if self.config.cache_optimize:
            try:
                from tools.cache_optimizer import get_cache_metrics

                metrics["cache"] = get_cache_metrics()
            except Exception:
                pass

        return metrics

    def get_configuration(self) -> Dict[str, Any]:
        """Get current optimization configuration."""
        return {
            "config": self.config.to_dict(),
            "initialized": self._initialized,
        }

    def enable_all(self) -> None:
        """Enable all optimizations (for testing/benchmarking)."""
        self.config.numa_aware = True
        self.config.cpu_affinity = True
        self.config.memory_pooling = True
        self.config.cache_optimize = True
        self.config.power_optimize = True
        self.config.syscall_reduce = True
        self._initialize()
        logger.info("All optimizations enabled")

    def disable_all(self) -> None:
        """Disable all optimizations."""
        self.config.numa_aware = False
        self.config.cpu_affinity = False
        self.config.memory_pooling = False
        self.config.cache_optimize = False
        self.config.power_optimize = False
        self.config.syscall_reduce = False
        logger.info("All optimizations disabled")

    def benchmark(self) -> Dict[str, Any]:
        """Run comprehensive benchmarks."""
        try:
            from tools.system_level_benchmark import run_all_benchmarks

            results = run_all_benchmarks()
            return results.to_dict()
        except Exception as e:
            logger.warning("Benchmarking failed: %s", e)
            return {"error": str(e)}


# Global manager instance
_manager: Optional[SystemOptimizationManager] = None
_manager_lock = threading.Lock()
_config = SystemOptimizationConfig()


def get_manager() -> SystemOptimizationManager:
    """Get global optimization manager."""
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = SystemOptimizationManager()
    return _manager


def execute_with_optimizations(
    tool_name: str,
    args: Dict[str, Any],
    execute_fn: Callable[[], Any],
) -> Any:
    """Execute a tool with system-level optimizations."""
    manager = get_manager()
    return manager.with_optimized_execution(tool_name, args, execute_fn)


def get_optimization_metrics() -> Dict[str, Any]:
    """Get current optimization metrics."""
    manager = get_manager()
    return manager.get_metrics()


def get_optimization_config() -> Dict[str, Any]:
    """Get optimization configuration."""
    manager = get_manager()
    return manager.get_configuration()


def run_benchmarks() -> Dict[str, Any]:
    """Run system-level benchmarks."""
    manager = get_manager()
    return manager.benchmark()


def enable_all_optimizations() -> None:
    """Enable all system-level optimizations."""
    manager = get_manager()
    manager.enable_all()


def disable_all_optimizations() -> None:
    """Disable all system-level optimizations."""
    manager = get_manager()
    manager.disable_all()
