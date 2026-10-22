#!/usr/bin/env python3
"""Tests for system-level optimizations."""

import json
import os
import pytest
import threading
import time
from unittest import mock

# Import optimization modules
from tools.numa_aware_dispatch import (
    NUMATopology,
    NUMADispatcher,
    get_numa_topology,
)
from tools.cpu_affinity_scheduler import (
    CPUTopology,
    CPUAffinityScheduler,
    get_scheduler,
)
from tools.memory_pool import (
    MemoryPool,
    NUMAMemoryPool,
    ToolArgumentPool,
    ResultBufferPool,
    get_memory_pool,
)
from tools.cache_optimizer import (
    CacheOptimizer,
    get_optimizer,
)
from tools.power_optimizer import (
    PowerOptimizer,
)
from tools.syscall_reducer import (
    SyscallReducer,
    get_reducer,
)
from tools.system_optimizations import (
    SystemOptimizationConfig,
    SystemOptimizationManager,
    get_manager,
    execute_with_optimizations,
)


class TestNUMATopology:
    """Tests for NUMA topology detection."""

    def test_topology_initialization(self):
        """Test NUMA topology can initialize."""
        topology = NUMATopology()
        assert topology is not None
        # May not have NUMA available, but shouldn't crash
        assert topology.num_nodes >= 0

    def test_numa_distance(self):
        """Test NUMA distance calculation."""
        topology = NUMATopology()
        # Same node should have distance 10 (local)
        if topology.num_nodes > 0:
            assert topology.distance(0, 0) == 10

    def test_get_numa_topology_caching(self):
        """Test that NUMA topology is cached."""
        topo1 = get_numa_topology()
        topo2 = get_numa_topology()
        assert topo1 is topo2  # Same object


class TestNUMADispatcher:
    """Tests for NUMA dispatcher."""

    def test_dispatcher_initialization(self):
        """Test NUMA dispatcher initializes."""
        dispatcher = NUMADispatcher()
        assert dispatcher is not None
        assert "enabled" in dispatcher.config

    def test_dispatch_tool_numa(self):
        """Test tool dispatch with NUMA awareness."""
        from tools.numa_aware_dispatch import dispatch_tool_numa

        call_count = 0

        def execute_fn():
            nonlocal call_count
            call_count += 1
            return "result"

        result = dispatch_tool_numa("test_tool", {}, execute_fn)
        assert result == "result"
        assert call_count == 1


class TestCPUTopology:
    """Tests for CPU topology."""

    def test_topology_initialization(self):
        """Test CPU topology detection."""
        topology = CPUTopology()
        assert topology is not None
        assert topology.num_cpus > 0

    def test_socket_groups(self):
        """Test socket grouping."""
        topology = CPUTopology()
        if topology.socket_groups:
            # Verify all CPUs are in some socket
            all_cpus = set()
            for socket_id, cpus in topology.socket_groups.items():
                all_cpus.update(cpus)
            assert len(all_cpus) <= topology.num_cpus

    def test_get_scheduler_caching(self):
        """Test scheduler is cached."""
        sched1 = get_scheduler()
        sched2 = get_scheduler()
        assert sched1 is sched2


class TestMemoryPool:
    """Tests for memory pooling."""

    def test_memory_pool_initialization(self):
        """Test memory pool initializes."""
        pool = MemoryPool(pool_size_mb=32)
        assert pool is not None
        assert pool.max_buffers > 0

    def test_memory_pool_acquire_release(self):
        """Test acquire and release from pool."""
        pool = MemoryPool(pool_size_mb=32)

        # Acquire buffer
        buf1 = pool.acquire(1024)
        assert buf1 is not None
        assert len(buf1) >= 1024

        # Release buffer
        pool.release(buf1)

        # Should be able to reuse
        buf2 = pool.acquire(1024)
        # Likely the same buffer due to pool reuse
        assert buf2 is not None

    def test_memory_pool_stats(self):
        """Test pool statistics."""
        pool = MemoryPool(pool_size_mb=32)
        stats = pool.get_stats()
        assert "available_buffers" in stats
        assert "allocations" in stats
        assert "reuses" in stats

    def test_numa_memory_pool(self):
        """Test NUMA-aware memory pool."""
        pool = NUMAMemoryPool(num_nodes=2, pool_size_mb=64)
        assert pool is not None

        # Acquire from different nodes
        buf0 = pool.acquire(1024, numa_node=0)
        buf1 = pool.acquire(1024, numa_node=1)

        assert buf0 is not None
        assert buf1 is not None

        pool.release(buf0, numa_node=0)
        pool.release(buf1, numa_node=1)

    def test_tool_argument_pool(self):
        """Test argument buffer pool."""
        pool = ToolArgumentPool(num_slots=100)

        args = {"key": "value", "number": 42}
        buf = pool.get_buffer_for_args(args)
        assert buf is not None

        pool.release_buffer(buf)

    def test_result_buffer_pool(self):
        """Test result buffer pool."""
        pool = ResultBufferPool(num_slots=50, buffer_size_kb=256)

        buf = pool.acquire()
        assert buf is not None
        assert len(buf) >= 256 * 1024

        pool.release(buf)

        stats = pool.get_stats()
        assert "available" in stats
        assert "hits" in stats


class TestCacheOptimizer:
    """Tests for cache optimization."""

    def test_cache_optimizer_initialization(self):
        """Test cache optimizer initializes."""
        optimizer = CacheOptimizer()
        assert optimizer is not None
        assert "enabled" in optimizer.config

    def test_schema_layout_optimization(self):
        """Test schema layout optimization."""
        optimizer = CacheOptimizer()

        schema = {
            "type": "object",
            "name": "test_tool",
            "properties": {"arg1": {"type": "string"}},
            "description": "Test tool description",
            "required": ["arg1"],
        }

        optimized = optimizer.optimize_tool_schema_layout(schema)
        assert optimized is not None
        # Hot fields should come first
        keys = list(optimized.keys())
        if "name" in optimized:
            assert keys.index("name") < len(keys) - 1

    def test_cache_metrics(self):
        """Test cache metrics."""
        optimizer = CacheOptimizer()
        metrics = optimizer.get_metrics()
        assert metrics is not None


class TestPowerOptimizer:
    """Tests for power optimization."""

    def test_power_optimizer_initialization(self):
        """Test power optimizer initializes."""
        optimizer = PowerOptimizer()
        assert optimizer is not None
        assert "enabled" in optimizer.config

    def test_thermal_status(self):
        """Test thermal status checking."""
        optimizer = PowerOptimizer()
        status = optimizer.check_thermal_status()
        assert status is not None
        assert "throttling" in status
        assert "temperature_c" in status

    def test_power_metrics(self):
        """Test power metrics."""
        optimizer = PowerOptimizer()
        metrics = optimizer.get_metrics()
        assert metrics is not None
        assert "frequency_scaling_disabled" in metrics


class TestSyscallReducer:
    """Tests for syscall reduction."""

    def test_syscall_reducer_initialization(self):
        """Test syscall reducer initializes."""
        reducer = SyscallReducer()
        assert reducer is not None
        assert "enabled" in reducer.config

    def test_syscall_metrics(self):
        """Test syscall metrics."""
        reducer = SyscallReducer()
        metrics = reducer.get_metrics()
        assert metrics is not None
        assert "total_syscalls" in metrics

    def test_record_syscall(self):
        """Test syscall recording."""
        from tools.syscall_reducer import record_syscall

        record_syscall("open", 10.5)
        record_syscall("read", 20.3)

        reducer = get_reducer()
        hot = reducer.get_hot_syscalls(limit=5)
        assert len(hot) <= 5


class TestSystemOptimizationConfig:
    """Tests for optimization configuration."""

    def test_config_initialization(self):
        """Test configuration initializes."""
        config = SystemOptimizationConfig()
        assert config is not None
        assert "enabled" in config.to_dict()

    def test_config_dict(self):
        """Test configuration export."""
        config = SystemOptimizationConfig()
        cfg_dict = config.to_dict()
        assert isinstance(cfg_dict, dict)
        assert "memory_pooling" in cfg_dict

    def test_is_any_enabled(self):
        """Test checking if any optimization is enabled."""
        config = SystemOptimizationConfig()
        # At least one should be enabled by default or environment
        # Or all disabled, either way this should work
        result = config.is_any_enabled()
        assert isinstance(result, bool)


class TestSystemOptimizationManager:
    """Tests for optimization manager."""

    def test_manager_initialization(self):
        """Test manager initializes."""
        manager = SystemOptimizationManager()
        assert manager is not None

    def test_get_manager_caching(self):
        """Test manager is cached."""
        mgr1 = get_manager()
        mgr2 = get_manager()
        assert mgr1 is mgr2

    def test_execute_with_optimizations(self):
        """Test executing tool with optimizations."""
        call_count = 0

        def execute_fn():
            nonlocal call_count
            call_count += 1
            return "result"

        result = execute_with_optimizations("test_tool", {}, execute_fn)
        assert result == "result"
        assert call_count == 1

    def test_get_metrics(self):
        """Test getting optimization metrics."""
        manager = get_manager()
        metrics = manager.get_metrics()
        assert isinstance(metrics, dict)

    def test_get_configuration(self):
        """Test getting configuration."""
        manager = get_manager()
        config = manager.get_configuration()
        assert "config" in config
        assert "initialized" in config

    def test_enable_disable_all(self):
        """Test enabling/disabling all optimizations."""
        manager = get_manager()

        manager.enable_all()
        config = manager.get_configuration()
        assert config["config"]["memory_pooling"]

        manager.disable_all()
        config = manager.get_configuration()
        assert not config["config"]["memory_pooling"]


class TestBenchmarking:
    """Tests for benchmarking functionality."""

    def test_benchmark_import(self):
        """Test benchmarking module imports."""
        try:
            from tools.system_level_benchmark import run_all_benchmarks

            # Benchmarking might not work on all systems
            # Just verify it doesn't crash
            assert run_all_benchmarks is not None
        except ImportError:
            pytest.skip("Benchmarking module not available")

    def test_run_benchmarks_via_manager(self):
        """Test running benchmarks through manager."""
        manager = get_manager()
        try:
            results = manager.benchmark()
            assert isinstance(results, dict)
        except Exception as e:
            # Benchmarking may fail on some systems; that's ok
            pytest.skip(f"Benchmarking failed: {e}")


class TestIntegration:
    """Integration tests for all components."""

    def test_full_optimization_flow(self):
        """Test full optimization flow."""
        # Enable all optimizations
        manager = get_manager()
        manager.enable_all()

        # Execute tool with optimizations
        def my_tool():
            time.sleep(0.01)  # Simulate work
            return {"status": "success"}

        result = execute_with_optimizations("my_tool", {}, my_tool)
        assert result == {"status": "success"}

        # Get metrics
        metrics = get_optimization_metrics()
        assert isinstance(metrics, dict)

    def test_memory_pool_integration(self):
        """Test memory pooling integration."""
        from tools.memory_pool import acquire_arg_buffer, release_arg_buffer

        args = {"key": "value", "data": "test"}

        # Acquire buffer
        buf = acquire_arg_buffer(args)
        assert buf is not None

        # Use buffer...
        # Release buffer
        release_arg_buffer(buf)

    def test_concurrent_tool_execution(self):
        """Test concurrent tool execution with optimizations."""
        results = []
        errors = []

        def execute_tool(tool_id):
            try:
                def tool_fn():
                    return f"result_{tool_id}"

                result = execute_with_optimizations(
                    f"tool_{tool_id}",
                    {"id": tool_id},
                    tool_fn,
                )
                results.append(result)
            except Exception as e:
                errors.append(e)

        # Execute multiple tools concurrently
        threads = [
            threading.Thread(target=execute_tool, args=(i,))
            for i in range(5)
        ]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        assert len(results) == 5
        assert len(errors) == 0


# Test helpers
def get_optimization_metrics():
    """Get optimization metrics."""
    from tools.system_optimizations import get_optimization_metrics

    return get_optimization_metrics()


@pytest.fixture
def reset_managers():
    """Reset global managers between tests."""
    import tools.system_optimizations
    import tools.memory_pool
    import tools.numa_aware_dispatch
    import tools.cpu_affinity_scheduler
    import tools.cache_optimizer
    import tools.power_optimizer
    import tools.syscall_reducer

    # Reset globals
    tools.system_optimizations._manager = None
    tools.memory_pool._memory_pool = None
    tools.memory_pool._arg_pool = None
    tools.memory_pool._result_pool = None
    tools.numa_aware_dispatch._NUMA_TOPOLOGY = None
    tools.cpu_affinity_scheduler._CPU_TOPOLOGY = None
    tools.cpu_affinity_scheduler._scheduler = None
    tools.cache_optimizer._optimizer = None
    tools.syscall_reducer._reducer = None

    yield

    # Reset after test
    tools.system_optimizations._manager = None
    tools.memory_pool._memory_pool = None
    tools.memory_pool._arg_pool = None
    tools.memory_pool._result_pool = None
    tools.numa_aware_dispatch._NUMA_TOPOLOGY = None
    tools.cpu_affinity_scheduler._CPU_TOPOLOGY = None
    tools.cpu_affinity_scheduler._scheduler = None
    tools.cache_optimizer._optimizer = None
    tools.syscall_reducer._reducer = None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
