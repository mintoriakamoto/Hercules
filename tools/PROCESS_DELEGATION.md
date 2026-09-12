# Process-Based Parallel Delegation

Hercules supports two execution modes for parallel subagent delegation:

## Execution Modes

### Thread-Based (Default)
- Uses `DaemonThreadPoolExecutor` (ThreadPoolExecutor with daemon threads)
- Lower overhead, faster startup
- Shared memory between threads
- Limited by Python GIL for CPU-bound work
- Better for I/O-bound subagent tasks

**Activation:** (default)
```bash
# No configuration needed - threads are the default
hercules chat
```

### Process-Based (New)
- Uses `ProcessPoolExecutor` with spawn context
- True parallelism on multi-core systems (no GIL)
- Separate Python interpreter per worker
- Higher IPC overhead, slower startup (~100ms per process)
- Better for CPU-bound or computationally heavy subagent work
- Cleaner isolation and resource cleanup

**Activation:**
```bash
export HERCULES_DELEGATION_EXECUTOR=process
hercules chat
```

## Configuration

### Environment Variable
```bash
# Set execution mode (default: "thread")
export HERCULES_DELEGATION_EXECUTOR=process

# Verify mode is active (check logs for executor type)
HERCULES_DELEGATION_EXECUTOR=process hercules chat 2>&1 | grep "executor"
```

### When to Use Each Mode

**Use threads (default) if:**
- Subagents perform mostly I/O operations (file reads, API calls, terminal commands)
- Fast startup is critical
- Subagents share significant state or need access to parent agent resources
- Total subagent count is small (< 4 concurrent)
- Memory overhead is a concern

**Use processes if:**
- Subagents perform compute-heavy work (analysis, parsing, reasoning)
- GIL contention is observed (high CPU usage per core < 100%)
- Subagents need isolation (independent Python state)
- Scalability to many concurrent subagents is needed (8+)
- Process startup cost is acceptable

## Implementation Details

### Architecture

```
┌──────────────────────────────────────────────────┐
│ Parent Agent (Main Process)                       │
│                                                  │
│  delegate_task()                                 │
│      ↓                                           │
│  _create_delegation_executor()                   │
│      ├─ "thread" → DaemonThreadPoolExecutor     │
│      └─ "process" → ProcessDelegationExecutor   │
│                                                  │
└──────────────────────────────────────────────────┘
         ↓ submit tasks via executor.submit()
    ┌────────────────────────┬────────────────────────┐
    │ Worker Pool            │ (threads or processes) │
    ├────────────────────────┼────────────────────────┤
    │ Future 1               │ Future 2               │ ...
    │ (serialized task)      │ (serialized task)      │
    └────────────────────────┴────────────────────────┘
         ↓ IPC serialization
    ┌────────────────────────┬────────────────────────┐
    │ Worker 1 Process       │ Worker 2 Process       │
    │ _run_single_child()    │ _run_single_child()    │
    │ AIAgent instance       │ AIAgent instance       │
    └────────────────────────┴────────────────────────┘
```

### Serialization Flow (Process Mode)

1. **Task Serialization** (parent → worker)
   - Task dict with goal, child config, parent agent state
   - Uses pickle for serialization
   - Pre-check for serializability before submit

2. **Execution** (worker process)
   - Deserialize task arguments
   - Create fresh AIAgent instance in worker process
   - Execute _run_single_child() with deserialized arguments
   - Capture result and exceptions

3. **Result Serialization** (worker → parent)
   - Result dict returned from _run_single_child()
   - Uses pickle for return value
   - Exceptions propagated through Future.result()

### Performance Characteristics

| Metric | Thread | Process |
|--------|--------|---------|
| Startup latency | ~1ms | ~100ms |
| IPC overhead | None | ~1-10ms per task |
| Memory per worker | ~8MB | ~40MB |
| GIL impact | High on CPU-bound | None |
| Context switching | OS threads | OS processes |
| Isolation | Shared memory | Separate heaps |

## Limitations

### Process-Based Mode
- Parent agent instance not available in worker (set to None)
- Terminal sessions must use task-isolated file operations
- MCP server connections not shared across processes
- Larger memory footprint (one Python interpreter per worker)
- Cannot use os.fork() (uses spawn context for cross-platform compatibility)

### Thread-Based Mode
- GIL limits parallelism for CPU-bound work
- Shared memory can lead to unexpected state sharing
- Higher GIL contention with many concurrent threads
- No isolation for debugging crashes

## Monitoring

### Check Current Mode
```bash
# Log will show executor type
HERCULES_DELEGATION_EXECUTOR=process hercules chat 2>&1 | grep -i "delegation executor"
# Output: "Using process-based delegation executor (max_workers=3)"
```

### Profile Execution
```bash
# With verbose logging
DEBUG=true HERCULES_DELEGATION_EXECUTOR=process hercules chat

# Monitor process creation (Linux)
watch -n 1 "ps aux | grep -E 'async-delegate|spawn'"
```

## Debugging

### Common Issues

**ProcessPoolExecutor fails to initialize:**
```
ERROR: Failed to initialize process executor: ...
FALLBACK: Using thread-based delegation
```
→ Check system supports multiprocessing (containers may restrict)
→ Verify PYTHONPATH includes necessary modules
→ Try thread mode as fallback

**Serialization errors:**
```
RuntimeError: Task serialization failed: ...
```
→ Check task contains only pickleable objects
→ Avoid complex agent instances, custom objects
→ Use task state dict instead of full objects

**Worker process hangs:**
→ Process executor has built-in timeout protection
→ Check logs for deadlocks in worker code
→ Verify terminal/file I/O doesn't block
→ Fall back to thread mode for debugging

## Future Enhancements

- [ ] Lazy process pool growth (start with 1, grow as needed)
- [ ] Shared state via multiprocessing.Manager() for select variables
- [ ] Process reuse strategy (keep processes warm between batches)
- [ ] Per-task timeout with process termination
- [ ] Profiling integration for process vs thread comparison
- [ ] Batch prioritization across workers

## References

- Python concurrent.futures: https://docs.python.org/3/library/concurrent.futures.html
- Multiprocessing: https://docs.python.org/3/library/multiprocessing.html
- GIL documentation: https://docs.python.org/3/glossary.html#term-GIL
