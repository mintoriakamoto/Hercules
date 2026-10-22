# GPU Acceleration Integration Guide

This document provides implementation details for integrating the GPU acceleration framework into Hercules' tool execution pipeline.

## Architecture Overview

```
model_tools.handle_function_call()
    ↓
tools/registry.dispatch() [INSERTION POINT 1: GPU routing decision]
    ↓
[GPU Path] ↓                          [CPU Path] ↓
gpu_kernel_dispatcher.route_to_gpu()  registry._tools[name].handler()
    ↓                                     ↓
[Validation] gpu_validator             [Normal execution]
    ↓
[Execution] (CPU-based)
    ↓
[Aggregation] gpu_result_aggregator
    ↓
Result returned to caller
```

## Integration Points

### 1. Argument Validation (INSERTION POINT 1)

**File**: `tools/registry.py`, method `dispatch()`

**Current Code** (line 668-710):
```python
def dispatch(self, name: str, args: dict, **kwargs) -> str | dict:
    """Execute a tool handler by name."""
    entry = self.get_entry(name)
    if not entry:
        return json.dumps({"error": f"Unknown tool: {name}"})
    try:
        # Phase 2: Check for JIT-compiled path first
        try:
            from tools.jit_compiler import get_compiled_tool, use_compiled_path
            # ... existing JIT code ...
        except (ImportError, ModuleNotFoundError):
            pass

        # Normal dispatch path
        start = time.perf_counter()
        if entry.is_async:
            from model_tools import _run_async
            result = _run_async(entry.handler(args, **kwargs))
        else:
            result = entry.handler(args, **kwargs)
        # ... rest of code ...
```

**Integration Change**:
```python
def dispatch(self, name: str, args: dict, **kwargs) -> str | dict:
    """Execute a tool handler by name."""
    entry = self.get_entry(name)
    if not entry:
        return json.dumps({"error": f"Unknown tool: {name}"})
    try:
        # Phase 2: Check for JIT-compiled path first
        try:
            from tools.jit_compiler import get_compiled_tool, use_compiled_path
            # ... existing JIT code ...
        except (ImportError, ModuleNotFoundError):
            pass

        # INSERTION POINT 1A: GPU argument validation (optional, before execution)
        try:
            from tools.gpu_kernel_dispatcher import get_gpu_dispatcher
            from tools.gpu_validator import get_gpu_validator
            
            dispatcher = get_gpu_dispatcher()
            validator = get_gpu_validator()
            
            # Validate arguments with GPU if batch size warrants it
            # This is optional—validation happens inside handlers anyway
            # But pre-validation can catch errors early
            if len(args) > 100:  # Only for "large" argument sets
                schema = entry.schema
                validation_result = validator.validate_batch(
                    tool_name=name,
                    schema=schema,
                    arguments_list=[args],  # Single call, but GPU may batch with others
                    use_gpu=None  # Auto-decide
                )
                if not validation_result.success_rate > 0.9:
                    return json.dumps({
                        "error": "Invalid tool arguments",
                        "validation_errors": validation_result.results[0].error_message,
                    }, ensure_ascii=False)
        except (ImportError, ModuleNotFoundError):
            pass  # GPU acceleration not available

        # Normal dispatch path
        start = time.perf_counter()
        if entry.is_async:
            from model_tools import _run_async
            result = _run_async(entry.handler(args, **kwargs))
        else:
            result = entry.handler(args, **kwargs)
        # ... rest of code ...
```

### 2. Tool Execution Batching (INSERTION POINT 2)

**File**: `agent/tool_executor.py`, function `execute_tool_calls_concurrent()`

**Current Code** (around line 200-300):
```python
def execute_tool_calls_concurrent(agent, tool_calls, ...):
    """Execute tool calls concurrently using thread pool."""
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=_MAX_TOOL_WORKERS)
    
    futures = {}
    for tool_call in tool_calls:
        future = executor.submit(
            _execute_single_tool_call,
            agent,
            tool_call,
            ...
        )
        futures[tool_call.id] = future
    
    results = {}
    for tool_call_id, future in futures.items():
        results[tool_call_id] = future.result(timeout=timeout)
    
    return results
```

**Integration Change**:
```python
def execute_tool_calls_concurrent(agent, tool_calls, ...):
    """Execute tool calls concurrently with GPU acceleration support."""
    
    # INSERTION POINT 2A: GPU batch pre-processing
    try:
        from tools.gpu_kernel_dispatcher import get_gpu_dispatcher
        from tools.gpu_validator import get_gpu_validator
        
        if len(tool_calls) >= 100:  # Only worth GPU overhead for large batches
            dispatcher = get_gpu_dispatcher()
            validator = get_gpu_validator()
            
            # Profile batch for GPU suitability
            arg_list = [tc.arguments for tc in tool_calls]
            # Could batch validate here, but usually validation happens in handlers
    except (ImportError, ModuleNotFoundError):
        pass  # GPU acceleration not available
    
    # Existing thread pool execution
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=_MAX_TOOL_WORKERS)
    
    futures = {}
    for tool_call in tool_calls:
        future = executor.submit(
            _execute_single_tool_call,
            agent,
            tool_call,
            ...
        )
        futures[tool_call.id] = future
    
    results = {}
    for tool_call_id, future in futures.items():
        results[tool_call_id] = future.result(timeout=timeout)
    
    # INSERTION POINT 2B: GPU batch result aggregation
    try:
        from tools.gpu_result_aggregator import get_gpu_result_aggregator
        
        if len(results) >= 1000:  # Only worth GPU overhead for large result batches
            aggregator = get_gpu_result_aggregator()
            
            # Pre-aggregate results for faster serialization
            # This improves throughput when returning to context compressor
            result_values = [r.get("result") for r in results.values() if r]
            agg_result = aggregator.aggregate_batch(
                result_values,
                use_gpu=None  # Auto-decide based on batch size
            )
            
            # Results are now cached for deduplication in serialization
    except (ImportError, ModuleNotFoundError):
        pass  # GPU acceleration not available
    
    return results
```

### 3. Result Serialization (INSERTION POINT 3)

**File**: `agent/tool_dispatch_helpers.py`, function `make_tool_result_message()`

**Integration Change**:
```python
def make_tool_result_message(tool_name: str, result: str, tool_id: str):
    """Create a tool result message for the conversation."""
    
    # INSERTION POINT 3A: GPU acceleration for result serialization
    try:
        from tools.gpu_result_aggregator import get_gpu_result_aggregator
        
        aggregator = get_gpu_result_aggregator()
        
        # If result is already a string, parse it for deduplication
        if isinstance(result, str):
            try:
                parsed = json.loads(result)
                # Check cache for identical results
                cached = aggregator.cache.get(aggregator._hash_result(parsed))
                if cached:
                    result = cached  # Use cached serialization
            except json.JSONDecodeError:
                pass
    except (ImportError, ModuleNotFoundError):
        pass  # GPU acceleration not available
    
    # Existing message creation
    return {
        "type": "tool_result",
        "tool_use_id": tool_id,
        "content": result,
    }
```

### 4. Profiling Integration (INSERTION POINT 4)

**File**: `tools/jit_profiler.py`, class `JITProfiler`

**Integration Change**:
```python
class JITProfiler:
    """Thread-safe tool call profiler."""
    
    def __init__(self, max_history: int = 10000):
        self.max_history = max_history
        self.stats: Dict[str, ToolExecutionStats] = {}
        self._lock = threading.RLock()
        self.total_calls = 0
        self.start_time = time.time()
        self.last_report_time = time.time()
        self._compilation_hints: Dict[str, dict] = {}
        
        # INSERTION POINT 4A: GPU profiling data
        self.gpu_suitability: Dict[str, float] = {}  # tool_name → suitability score
        self.gpu_recommendations: Dict[str, str] = {}  # tool_name → "cpu"/"gpu"/"hybrid"
    
    def record_call(self, tool_name: str, duration_ms: float, success: bool = True):
        """Record a tool execution."""
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
            
            # INSERTION POINT 4B: Update GPU suitability recommendation
            try:
                from tools.gpu_kernel_dispatcher import get_gpu_dispatcher
                
                dispatcher = get_gpu_dispatcher()
                
                # Profile tool for GPU suitability (call every 100 ops)
                if stats.call_count % 100 == 0:
                    char = dispatcher.tool_characteristics.get(tool_name)
                    if char:
                        self.gpu_suitability[tool_name] = char.gpu_suitability_score
                        self.gpu_recommendations[tool_name] = char.recommended_device
            except (ImportError, ModuleNotFoundError):
                pass  # GPU not available
```

## Configuration Parameters

Add to `hercules_cli/config.py`:

```python
class GPUAccelerationConfig:
    """GPU acceleration settings."""
    
    # Global enable/disable
    GPU_ENABLED = env_bool("HERCULES_GPU_ENABLED", default=True)
    
    # Validation acceleration
    GPU_VALIDATION_MIN_BATCH = env_int(
        "HERCULES_GPU_VALIDATION_MIN_BATCH",
        default=100
    )
    GPU_VALIDATION_ENABLED = env_bool(
        "HERCULES_GPU_VALIDATION_ENABLED",
        default=True
    )
    
    # Serialization acceleration
    GPU_SERIALIZATION_MIN_BATCH = env_int(
        "HERCULES_GPU_SERIALIZATION_MIN_BATCH",
        default=500
    )
    GPU_SERIALIZATION_ENABLED = env_bool(
        "HERCULES_GPU_SERIALIZATION_ENABLED",
        default=True
    )
    
    # Memory management
    GPU_MAX_MEMORY_MB = env_int(
        "HERCULES_GPU_MAX_MEMORY_MB",
        default=2048
    )
    GPU_MEMORY_FALLBACK_PERCENT = env_int(
        "HERCULES_GPU_MEMORY_FALLBACK_PERCENT",
        default=10
    )
    
    # Caching
    GPU_CACHE_ENABLED = env_bool(
        "HERCULES_GPU_CACHE_ENABLED",
        default=True
    )
    GPU_CACHE_SIZE = env_int(
        "HERCULES_GPU_CACHE_SIZE",
        default=10000
    )
    
    # Profitability thresholds
    GPU_MIN_SPEEDUP_FACTOR = env_float(
        "HERCULES_GPU_MIN_SPEEDUP_FACTOR",
        default=1.5
    )
    GPU_MIN_CONFIDENCE = env_float(
        "HERCULES_GPU_MIN_CONFIDENCE",
        default=0.5
    )
    
    # Debugging & monitoring
    GPU_PROFILING_ENABLED = env_bool(
        "HERCULES_GPU_PROFILING_ENABLED",
        default=False
    )
    GPU_LOG_EVERY_N_CALLS = env_int(
        "HERCULES_GPU_LOG_EVERY_N_CALLS",
        default=1000
    )
```

## Deployment Checklist

- [ ] Create `tools/gpu_kernel_dispatcher.py` (✅ Done)
- [ ] Create `tools/gpu_validator.py` (✅ Done)
- [ ] Create `tools/gpu_result_aggregator.py` (✅ Done)
- [ ] Create `tools/gpu_benchmarking.py` (✅ Done)
- [ ] Add GPU detection at startup: `gpu_kernel_dispatcher.get_gpu_device()`
- [ ] Register configuration options in `hercules_cli/config.py`
- [ ] Integrate validation (INSERTION POINT 1): `tools/registry.py`
- [ ] Integrate batching (INSERTION POINT 2): `agent/tool_executor.py`
- [ ] Integrate serialization (INSERTION POINT 3): `agent/tool_dispatch_helpers.py`
- [ ] Integrate profiling (INSERTION POINT 4): `tools/jit_profiler.py`
- [ ] Add logging configuration for GPU module
- [ ] Create comprehensive test suite: `tests/tools/test_gpu_*.py`
- [ ] Document in CLAUDE.md
- [ ] Add GPU monitoring dashboard (optional)
- [ ] Performance regression tests (optional)

## Testing Strategy

### Unit Tests
```python
# tests/tools/test_gpu_validator.py
def test_validation_correctness():
    """Ensure GPU validation matches CPU."""
    # Compare results from GPU and CPU validators
    # Test edge cases, type coercion, enums, ranges
    
# tests/tools/test_gpu_aggregator.py
def test_serialization_correctness():
    """Ensure GPU serialization matches CPU."""
    # Compare JSON output from GPU and CPU paths
    # Test caching, deduplication, format preservation
    
# tests/tools/test_gpu_dispatcher.py
def test_gpu_availability_detection():
    """Test GPU detection and fallback."""
    # Verify CUDA detection works
    # Test graceful fallback when GPU unavailable
```

### Integration Tests
```python
# tests/integration/test_gpu_tool_execution.py
def test_gpu_accelerated_tool_execution():
    """Test end-to-end tool execution with GPU."""
    # Run 1000 tool calls with GPU enabled
    # Measure speedup vs CPU baseline
    # Verify correctness of results

def test_gpu_fallback_on_error():
    """Test fallback to CPU on GPU errors."""
    # Simulate GPU OOM
    # Verify CPU fallback works
    # Check error logging

def test_mixed_gpu_cpu_execution():
    """Test mixed GPU/CPU execution."""
    # Some tools use GPU, others use CPU
    # Verify results are consistent
```

### Performance Tests
```python
# tests/performance/test_gpu_benchmarks.py
def test_validation_speedup():
    """Benchmark validation acceleration."""
    # Run benchmark_validation_operation()
    # Verify speedup meets expectations (>20x for large batches)
    
def test_serialization_speedup():
    """Benchmark serialization acceleration."""
    # Run benchmark_serialization_operation()
    # Verify speedup meets expectations (>10x for large batches)
    
def test_scaling_characteristics():
    """Test scaling with batch size."""
    # Verify speedup increases with batch size
    # Identify sweet spot batch sizes
```

## Monitoring & Observability

### Metrics to Track
- GPU device availability (bool)
- GPU memory used (MB)
- GPU utilization (%)
- Per-tool GPU recommendation
- Validation operations: GPU vs CPU count
- Serialization operations: GPU vs CPU count
- Cache hit rate (%)
- Fallback events (count, reason)
- GPU error rate

### Logging Points
```python
logger.info("GPU acceleration available: %s", device)
logger.debug("Tool %s: GPU suitability %.2f, recommended %s", 
             tool_name, score, device)
logger.warning("GPU validation failed, falling back to CPU: %s", error)
logger.info("GPU batch validation: %d items in %.1f ms, speedup %.1fx",
            batch_size, time_ms, speedup)
```

### Dashboard
Consider adding to Hercules' monitoring:
- GPU acceleration status (enabled/disabled, device type)
- Speedup trends over time
- Per-tool GPU recommendations
- GPU memory pressure
- Fallback rate trends

## Troubleshooting Guide

### GPU Not Detected
```
Problem: GPU acceleration disabled despite NVIDIA GPU present
Solution:
  1. Verify CUDA runtime: `nvidia-smi`
  2. Check Python env: `python -c "import numba; print(numba.cuda.is_available())"`
  3. Enable GPU: `HERCULES_GPU_ENABLED=1`
```

### GPU Memory Exhaustion
```
Problem: Out-of-memory errors on GPU
Solution:
  1. Reduce GPU batch size: `HERCULES_GPU_VALIDATION_MIN_BATCH=10`
  2. Reduce max GPU memory: `HERCULES_GPU_MAX_MEMORY_MB=1024`
  3. Enable CPU fallback: `HERCULES_GPU_MEMORY_FALLBACK_PERCENT=20`
```

### Slower with GPU Enabled
```
Problem: GPU version is slower than CPU
Solution:
  1. Check batch size (needs 100+ for profitability)
  2. Profile tool: `gpu_dispatcher.analyze_profitability(tool_name)`
  3. Disable GPU for this tool in config
```

## Performance Expectations

**Conservative Estimate (Recommended)**:
- Validation: 5-10x speedup (requires 1000+ batch)
- Serialization: 3-5x speedup (requires 5000+ batch)
- Overall impact: 5-15% agent speedup on typical workloads

**Optimistic Estimate (Best Case)**:
- Validation: 30-50x speedup (extreme batch sizes)
- Serialization: 20-30x speedup (cache hits, large results)
- Overall impact: 20-50% agent speedup on batched workloads

**Realistic Production Estimate**:
- 10-20% improvement for typical agent interactions
- 50x+ improvement for batch operations (100+ tool calls)
- Highly workload-dependent (validation-heavy vs execution-heavy)
