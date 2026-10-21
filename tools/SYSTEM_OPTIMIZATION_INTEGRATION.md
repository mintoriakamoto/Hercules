# Integration Guide: System-Level Optimizations

## Quick Start

### 1. Enable Optimizations (Minimal Setup)

Add to `agent/tool_executor.py` around line 359 (in `execute_tool_calls_concurrent`):

```python
from tools.system_optimizations import execute_with_optimizations

def execute_tool_calls_concurrent(
    agent,
    assistant_message,
    messages: list,
    effective_task_id: str,
    api_call_count: int = 0,
) -> None:
    """Execute multiple tool calls concurrently using a thread pool."""
    
    # ... existing code ...
    
    # In the tool execution loop (around line 500+):
    for tool_call in tool_calls:
        function_name = tool_call.function.name
        function_args, malformed_args_result = _parse_tool_arguments(
            tool_call.function.arguments
        )
        
        if malformed_args_result is not None:
            # ... existing error handling ...
            continue
        
        # WRAP TOOL EXECUTION WITH OPTIMIZATIONS
        def execute_tool_with_context():
            return invoke_tool(
                agent, 
                function_name, 
                function_args,
                tool_call,
                messages
            )
        
        result = execute_with_optimizations(
            function_name,
            function_args,
            execute_tool_with_context
        )
        
        # ... rest of existing code ...
```

### 2. Configure Environment

Set environment variables before running Hercules:

```bash
# Enable memory pooling (default optimization)
export MEMORY_POOLING_ENABLED=true

# Optional: enable CPU affinity for multi-socket systems
export CPU_AFFINITY_ENABLED=false  # Set to true for 8+ core systems

# Optional: enable NUMA dispatch for >2 socket systems
export NUMA_DISPATCH_ENABLED=false  # Set to true for 4+ socket systems

# Optional: enable power optimization (requires root)
export POWER_OPTIMIZER_ENABLED=false

# Start Hercules
hercules
```

### 3. Verify Integration

Check if optimizations are active:

```python
from tools.system_optimizations import get_optimization_config, get_optimization_metrics

# Check configuration
config = get_optimization_config()
print(f"Optimizations enabled: {config['config']['enabled']}")
print(f"Memory pooling: {config['config']['memory_pooling']}")

# Check runtime metrics
metrics = get_optimization_metrics()
print(f"Memory pool stats: {metrics.get('memory_pool')}")
```

## Detailed Integration Steps

### Step 1: Import Optimization Module

In `agent/tool_executor.py`, add at the top with other imports:

```python
from tools.system_optimizations import execute_with_optimizations
```

### Step 2: Refactor Tool Execution

Find the concurrent execution loop (around line 450-550 in `tool_executor.py`):

**Before:**
```python
for tool_call in tool_calls:
    # ... argument parsing ...
    result = invoke_tool(agent, function_name, function_args)
    # ... handle result ...
```

**After:**
```python
for tool_call in tool_calls:
    # ... argument parsing ...
    
    # Capture execution in a closure for optimization wrapper
    def execute_fn(fn=function_name, args=function_args):
        return invoke_tool(agent, fn, args)
    
    # Execute with system-level optimizations
    result = execute_with_optimizations(function_name, function_args, execute_fn)
    # ... handle result ...
```

### Step 3: Add Metrics Logging (Optional)

Add performance metrics logging:

```python
import logging
from tools.system_optimizations import get_optimization_metrics

logger = logging.getLogger(__name__)

def _log_optimization_metrics() -> None:
    """Log system optimization metrics."""
    try:
        metrics = get_optimization_metrics()
        if metrics.get("memory_pool"):
            mp_stats = metrics["memory_pool"]
            logger.info(
                "Memory pool: reuses=%d allocations=%d gc_pauses_avoided=%d",
                mp_stats.get("reuses", 0),
                mp_stats.get("allocations", 0),
                mp_stats.get("gc_pauses_avoided", 0),
            )
    except Exception as e:
        logger.debug("Could not log optimization metrics: %s", e)

# Call periodically (e.g., after each turn)
_log_optimization_metrics()
```

### Step 4: Update Tool Executor Tests

Add to `tests/agent/test_tool_executor.py`:

```python
import os
from tools.system_optimizations import execute_with_optimizations

def test_execute_tool_with_optimizations():
    """Test tool execution with system optimizations."""
    
    # Enable memory pooling for test
    os.environ["MEMORY_POOLING_ENABLED"] = "true"
    
    executed = False
    
    def test_tool():
        nonlocal executed
        executed = True
        return "test_result"
    
    # Execute with optimization wrapper
    result = execute_with_optimizations(
        "test_tool",
        {"arg": "value"},
        test_tool
    )
    
    assert executed
    assert result == "test_result"
```

## Advanced Configuration

### Via Configuration File

Create `~/.hercules/system_optimizations.json`:

```json
{
  "version": 1,
  "optimizations": {
    "enabled": true,
    "memory_pooling": {
      "enabled": true,
      "pool_size_mb": 256
    },
    "cpu_affinity": {
      "enabled": false,
      "cache_aware": true
    },
    "numa_aware": {
      "enabled": false,
      "pin_threads": true
    },
    "cache_optimize": {
      "enabled": false,
      "use_huge_pages": false
    },
    "power_optimize": {
      "enabled": false,
      "disable_freq_scaling": false
    },
    "syscall_reduce": {
      "enabled": false
    }
  },
  "profiling": {
    "enabled": false,
    "log_metrics_every_n_tools": 100
  }
}
```

Load configuration:

```python
import json
from pathlib import Path
from tools.system_optimizations import get_manager

def load_optimization_config():
    """Load optimization config from file."""
    config_path = Path.home() / ".hercules" / "system_optimizations.json"
    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)
        
        manager = get_manager()
        for key, value in config.get("optimizations", {}).items():
            if hasattr(manager.config, key):
                setattr(manager.config, key, value.get("enabled", False))
```

### Runtime Configuration

Change settings at runtime:

```python
from tools.system_optimizations import get_manager

manager = get_manager()

# Enable all
manager.enable_all()

# Disable all
manager.disable_all()

# Enable specific optimization
manager.config.memory_pooling = True
manager.config.cpu_affinity = False

print(manager.get_configuration())
```

## Performance Monitoring

### Enable Detailed Metrics

```python
from tools.system_optimizations import get_optimization_metrics
import json

metrics = get_optimization_metrics()
print(json.dumps(metrics, indent=2))
```

Example output:
```json
{
  "memory_pool": {
    "node_0": {
      "available_buffers": 8,
      "allocations": 145,
      "reuses": 892,
      "gc_pauses_avoided": 23
    }
  },
  "power": {
    "frequency_scaling_disabled": false,
    "p_state_ratio": 100,
    "thermal_throttle_events": 0,
    "current_temp_c": 52.0
  },
  "syscalls": {
    "total_syscalls": 8432,
    "batched_calls": 120,
    "average_batch_size": "4.2",
    "estimated_reduction": "1.2x"
  }
}
```

### Benchmark Before/After

```bash
# Run baseline benchmark
python tools/system_level_benchmark.py > /tmp/baseline.json

# Enable optimizations
export MEMORY_POOLING_ENABLED=true
export CPU_AFFINITY_ENABLED=true

# Run optimized benchmark
python tools/system_level_benchmark.py > /tmp/optimized.json

# Compare
python -c "
import json
with open('/tmp/baseline.json') as f:
    baseline = json.load(f)
with open('/tmp/optimized.json') as f:
    optimized = json.load(f)

baseline_speedup = baseline['total_estimated_speedup_x']
optimized_speedup = optimized['total_estimated_speedup_x']
improvement = optimized_speedup / baseline_speedup

print(f'Baseline speedup: {baseline_speedup:.1f}x')
print(f'Optimized speedup: {optimized_speedup:.1f}x')
print(f'Improvement: {improvement:.1f}x')
"
```

## Troubleshooting Integration

### Optimization Not Running

Check if optimizations are enabled:

```python
from tools.system_optimizations import get_optimization_config

config = get_optimization_config()
if not config['config']['enabled']:
    print("Optimizations are disabled!")
else:
    print(f"Active optimizations: {config['config']}")
```

### Memory Pool OOM

If memory grows unbounded:

```python
from tools.memory_pool import get_memory_pool

pool = get_memory_pool()
stats = pool.get_stats()
print(f"Pool stats: {stats}")

# Reduce pool size
import os
os.environ["MEMORY_POOL_SIZE_MB"] = "128"
```

### CPU Affinity Not Working

Verify CPU topology detection:

```python
from tools.cpu_affinity_scheduler import get_scheduler

scheduler = get_scheduler()
print(f"CPU count: {scheduler.topology.num_cpus}")
print(f"L3 caches: {len(scheduler.topology.l3_cache_groups)}")
print(f"Sockets: {len(scheduler.topology.socket_groups)}")
```

## Compatibility

### Tested With

- Python 3.10+
- Linux 5.10+ (for NUMA and CPU topology detection)
- Multi-core systems (benefits scale with core count)
- NUMA systems (2+ socket systems get 2-5x speedup)

### Known Limitations

- NUMA detection requires `/sys/devices/system/node` or `numactl`
- CPU affinity requires Linux `sched_setaffinity` support
- Huge pages require `/sys/kernel/mm/transparent_hugepage` access
- Power optimization may require root access to change governors

## Migration Path

### Phase 1: Enable Memory Pooling (Minimal Risk)
- Low overhead (~1-2ms per tool)
- Works on all systems
- GC pause reduction: 10-50ms

```bash
export MEMORY_POOLING_ENABLED=true
```

### Phase 2: Add CPU Affinity (Multi-Socket Systems)
- Requires 8+ cores or 2+ sockets
- Risk: context switch overhead if misconfigured
- Cache benefit: 2-5x on multi-socket systems

```bash
export CPU_AFFINITY_ENABLED=true
```

### Phase 3: Add NUMA Dispatch (4+ Socket Systems)
- Only beneficial on NUMA systems
- Requires topology detection
- Benefit: 2-5x on NUMA systems

```bash
export NUMA_DISPATCH_ENABLED=true
```

### Phase 4: Advanced Optimizations (Tuning)
- Requires profiling and benchmarking
- May have system-specific trade-offs
- Benefit: 1.2-2x additional speedup

```bash
export CACHE_OPTIMIZER_ENABLED=true
export POWER_OPTIMIZER_ENABLED=true
export SYSCALL_REDUCE_ENABLED=true
```

## Support

For issues or questions:

1. Check `SYSTEM_LEVEL_OPTIMIZATIONS.md` for detailed documentation
2. Run `python tools/system_level_benchmark.py` to profile your system
3. Enable verbose logging: `export SYSTEM_OPT_VERBOSE=true`
4. Check system metrics: `get_optimization_metrics()`
