# Phase 3: Distributed Tool Call Acceleration

## Objective

Design and prototype infrastructure to distribute tool calls across multiple machines/processes to achieve **1B+ tool calls/sec globally** with **sub-millisecond latency**. Phase 3 focuses on **network-efficient distributed dispatch** with zero-copy schema access and deterministic verification across nodes.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      Client Applications                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│         Distributed Tool Dispatcher Cluster                      │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ DistributedDispatcher (Single Coordinator)              │    │
│  │  • Consistent hash ring (tool → node mapping)           │    │
│  │  • Load balancing with dynamic reweighting              │    │
│  │  • Batching requests (10ms timeout, 100 calls)          │    │
│  │  • Fault tolerance & automatic failover                 │    │
│  └─────────────────────────────────────────────────────────┘    │
│                         ↓ ↓ ↓                                    │
│  ┌──────────────┬──────────────┬──────────────┐                 │
│  │   Node 1     │   Node 2     │   Node 3     │    ...          │
│  │  ┌────────┐  │  ┌────────┐  │  ┌────────┐  │                 │
│  │  │ToolPool│  │  │ToolPool│  │  │ToolPool│  │ (Connection    │
│  │  │Manager │  │  │Manager │  │  │Manager │  │  pools with    │
│  │  └────────┘  │  └────────┘  │  └────────┘  │  health checks)│
│  │       ↓      │       ↓       │       ↓      │                 │
│  │  ┌─────────────────────────────────────┐   │                 │
│  │  │ Shared Memory Schema Cache (mmap)    │   │                 │
│  │  │ • Zero-copy access (no serialization)│   │                 │
│  │  │ • Generation counter for invalidation│   │                 │
│  │  │ • 100% hit rate for hot tools        │   │                 │
│  │  └─────────────────────────────────────┘   │                 │
│  │       ↓      │       ↓       │       ↓      │                 │
│  │  ┌─────────────────────────────────────┐   │                 │
│  │  │ Distributed Consensus Verifier       │   │                 │
│  │  │ • Quorum-based verification (3/N)   │   │                 │
│  │  │ • Cached proofs (3600s TTL)         │   │                 │
│  │  │ • Deterministic result hashing      │   │                 │
│  │  └─────────────────────────────────────┘   │                 │
│  └──────────────┴──────────────┴──────────────┘                 │
└─────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. **DistributedDispatcher** (`tools/distributed_dispatch.py`)

Central coordinator managing tool calls across the cluster.

**Key Features:**
- **Consistent Hashing Ring**: Deterministic tool-to-node mapping using SHA-256
  - 150 virtual nodes per physical node (configurable)
  - Smooth rebalancing on node failure
  - O(log N) lookup via binary search
  
- **Load Balancing**:
  - Weighted consistent hashing (node weights reflect capacity)
  - Dynamic reweighting based on actual load
  - Request batching to reduce RPC overhead
  
- **Fault Tolerance**:
  - N-replica storage (default 3) for fault tolerance
  - Automatic failover to replicas on primary failure
  - Node health tracking with error rate thresholds
  - Exponential backoff on persistent failures
  
- **Request Batching**:
  - Groups requests destined for same node
  - Timeout-based batch sending (10ms default)
  - Size-based batch sending (100 calls default)
  - Reduces RPC overhead by 10-50x

**API:**
```python
dispatcher = DistributedDispatcher()
dispatcher.add_node("node-1", "localhost", 9001, weight=1.0)

# Single call
result = dispatcher.dispatch_call(ToolCallRequest(...))

# Batch calls (grouped by destination)
results = dispatcher.dispatch_batch([req1, req2, req3, ...])

# Stats
stats = dispatcher.get_stats()
```

### 2. **Memory-Mapped Schema Cache** (`tools/distributed_cache.py`)

Zero-copy schema access across processes using shared memory.

**Design:**
- Schemas stored in mmap file (`/dev/shm/.hercules_schema_cache`)
- Atomic generation counter for cache invalidation
- Lock-free reads (readers don't block writers)
- Automatic cleanup on corruption

**Benefits:**
- **100% cache hit rate** for repeated tool calls
- **Zero deserialization overhead** (direct pointer access)
- **Inter-process sharing** (eliminates duplication)
- **Sub-microsecond access latency**

**API:**
```python
cache = get_schema_cache()
cache.put("read_file", {"name": "read_file", ...})

schema = cache.get("read_file")  # ~0.5us latency

# Invalidate on schema change
cache.invalidate("read_file")

# Get stats
stats = cache.get_stats()  # {hits, misses, hit_rate_percent, ...}
```

### 3. **Tool Pool Manager** (`tools/tool_pool.py`)

Connection pooling and health management for remote nodes.

**Features:**
- **Fixed-size connection pools** per node
- **Persistent connections** (avoid handshake overhead)
- **Health checks** via heartbeats (5s interval)
- **Backpressure handling** with queue management
- **Exponential backoff** on failures
- **Latency tracking** (p50, p95, p99)

**Design Rationale:**
- Pools reuse connections to avoid TCP handshake (~1ms)
- Health checks detect dead nodes within 10 seconds
- Backoff prevents thundering herd on cascade failure
- Per-pool metrics enable adaptive routing

**API:**
```python
pool = ToolPool("localhost", 9001, pool_size=10)

success, result = pool.execute_request(request, timeout_ms=30000)
metrics = pool.get_metrics()

# Cluster-wide management
cluster = ToolPoolCluster(pool_size=10)
cluster.add_pool("node-1", "localhost", 9001)
cluster.start_health_checks(interval_seconds=5)
```

### 4. **Distributed Consensus** (`agent/consensus/distributed.py`)

Extends local consensus to verify tool calls across multiple nodes.

**Architecture:**
- **Quorum-based Verification**: Result is valid if N nodes agree
- **Deterministic Hashing**: Results compared via SHA-256 hashes
- **Proof Caching**: Stores verification results with TTL
- **Cross-node Comparison**: Finds consensus among replicated calls

**Invariants:**
1. All replicas execute identical tool call (same args)
2. Results are compared deterministically (no fuzzy matching)
3. Majority consensus is the ground truth
4. Failed nodes don't prevent verification (replicas save us)

**API:**
```python
verifier = get_distributed_verifier()

node_results = {
    "node-1": {"result": "ok", ...},
    "node-2": {"result": "ok", ...},
    "node-3": {"result": "ok", ...},
}

verification = verifier.verify_distributed(
    "read_file",
    {"path": "/etc/passwd"},
    node_results
)

print(f"Verified: {verification.is_verified}")
print(f"Agreeing nodes: {verification.agreeing_nodes}")
print(f"Latency: {verification.verification_time_ms}ms")
```

## Performance Targets

### Latency
- **Schema lookup**: < 1 microsecond (zero-copy cache)
- **Consistent hash lookup**: < 10 microseconds
- **Single dispatch**: < 1 millisecond (local execution)
- **Network RPC**: 1-10 milliseconds (deployment-dependent)
- **Distributed consensus**: < 5 milliseconds

### Throughput
- **Single process**: 100K-500K calls/sec (Hercules loop limited)
- **Single node (10 processes)**: 1M-5M calls/sec
- **Cluster (5 nodes × 10 processes)**: 5M-25M calls/sec
- **Target (100 nodes × 10 processes)**: 500M-2.5B calls/sec

### Resource Usage
- **Memory per node**: ~500MB base + schema cache
- **Schema cache**: 256MB mmap (configurable)
- **Connection pools**: ~100KB per pool (10 connections × ~10KB)
- **CPU per node**: ~50% for 1M calls/sec

## Integration Points

### With Existing Tool Registry

The distributed dispatcher integrates transparently with existing tool registry:

```python
# Phase 3 adaptation: tool dispatch
def dispatch_tool_call(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch tool call, using distributed infrastructure if available."""
    
    # Try distributed dispatcher first (if available)
    if _distributed_dispatcher:
        request = ToolCallRequest(
            tool_name=tool_name,
            args=args,
            request_id=generate_request_id(),
        )
        result = _distributed_dispatcher.dispatch_call(request)
        return result.result if result.success else {"error": result.error}
    
    # Fall back to local execution
    return _execute_tool_locally(tool_name, args)
```

### With Existing Consensus System

Distributed consensus extends single-node consensus:

```python
# Verify tool call across multiple executions
if replication_factor > 1:
    # Execute on N nodes
    node_results = execute_replicated(tool_name, args, n=3)
    
    # Verify via distributed consensus
    verification = verify_tool_call_distributed(tool_name, args, node_results)
    
    if not verification.is_verified:
        raise ConsensusFailure(f"Nodes disagreed: {verification}")
```

## Deployment Model

### Single-Machine Deployment
- All dispatch nodes on same machine
- Uses socket for inter-process communication
- Suitable for development and testing
- Can achieve 5-25M calls/sec on modern hardware

### Multi-Machine Deployment
- Nodes across multiple servers
- Uses TCP/gRPC for inter-node communication
- Requires network configuration (DNS, load balancing)
- Can scale to 1B+ calls/sec globally

### Kubernetes Deployment
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hercules-dispatch-node
spec:
  replicas: 50  # 50 nodes globally
  template:
    spec:
      containers:
      - name: dispatch-node
        image: hercules:latest
        env:
        - name: HERCULES_DISPATCH_PORT
          value: "9001"
        - name: HERCULES_POOL_SIZE
          value: "10"
        resources:
          requests:
            cpu: "4"
            memory: "2Gi"
```

## Trade-offs

### Centralized Coordinator vs. Distributed
**Chosen: Centralized**
- ✓ Simpler to reason about
- ✓ No consensus overhead
- ✓ Single failure domain (mitigated by replicas)
- ✗ Coordinator is potential bottleneck
  - **Mitigation**: Hash ring computations are O(log N), batching reduces RPC frequency
  - **Scale**: Can coordinate 1000+ nodes with <10% CPU

### Memory-Mapped Schemas vs. Network Caching
**Chosen: Memory-Mapped**
- ✓ Zero-copy access (sub-microsecond)
- ✓ No network latency
- ✓ Eliminates schema serialization
- ✗ Limited to single machine per cache instance
  - **Mitigation**: Each node has its own cache; schemas are small (<1KB)

### Quorum Verification vs. Single-Node
**Chosen: Quorum**
- ✓ Detects Byzantine failures (one bad node)
- ✓ Tolerates transient failures
- ✓ Deterministic (no opinion-based ranking)
- ✗ 3x cost for critical operations
  - **Mitigation**: Cached proofs eliminate re-verification; not all calls verified

### Batching vs. Individual RPCs
**Chosen: Batching**
- ✓ 10-50x throughput improvement
- ✓ Better network utilization
- ✓ Reduces coordination overhead
- ✗ 10ms latency added per batch
  - **Mitigation**: Timeout-based (sends early if network idle)

## Validation Criteria

### Phase 3 Success Metrics

1. **Distributed dispatch can route 100M+ calls/sec**
   - Benchmark: bench_phase3.py::benchmark_end_to_end_scaling
   - Target: 100M calls/sec on 10-node cluster
   - Success: Achieve within 50% of target

2. **Sub-millisecond dispatch latency**
   - Benchmark: All latency measurements
   - Target: P99 < 1ms for dispatch, < 5ms for network RPC
   - Success: P99 dispatch latency < 1ms

3. **Consistent hashing distributes uniformly**
   - Benchmark: benchmark_hash_ring_distribution
   - Target: StdDev/Mean < 5%
   - Success: Achieve target distribution

4. **Zero-copy schema access**
   - Benchmark: benchmark_schema_cache
   - Target: Sub-microsecond access, 100% hit rate
   - Success: < 1us access latency, > 99% hit rate

5. **Fault tolerance with minimal overhead**
   - Benchmark: benchmark_fault_tolerance
   - Target: >95% success rate with 1 node down
   - Success: Maintain >95% with 2+ nodes down

6. **Distributed consensus scales efficiently**
   - Benchmark: benchmark_distributed_consensus
   - Target: < 5ms verification for 3-replica quorum
   - Success: Achieve target with > 90% cached proofs

## Benchmark Results

Run the comprehensive benchmark suite:

```bash
python -m tools.bench_phase3 --num-calls 100000 --verbose
```

This generates:
- Hash ring distribution analysis
- Load balancing uniformity
- Batching efficiency comparison
- Schema cache performance
- Distributed consensus latency
- Fault tolerance behavior
- End-to-end scaling metrics

Results are saved to `tools/bench_phase3_results.json`.

## Future Enhancements

### Phase 3.1: Adaptive Routing
- Route similar tools to same nodes (locality optimization)
- Learn optimal batch sizes per node type
- Predict failures before they occur

### Phase 3.2: Edge Dispatch
- Push dispatch nodes to edge (CDN, user premises)
- Local schema caches synchronized via gossip
- Reduced latency for globally-distributed users

### Phase 3.3: Persistent Dispatch
- Store tool call results for recovery
- Replay execution on verification failure
- Audit trail for compliance

### Phase 3.4: Intelligent Batching
- Dynamic batch size based on network conditions
- Priority queue (critical calls before background)
- Request coalescing (identical calls executed once)

## Security Considerations

1. **Tool Call Isolation**
   - Each node is sandboxed (separate process)
   - Tool schemas validated before dispatch
   - Args sanitized to prevent injection

2. **Result Verification**
   - Distributed consensus detects tampering
   - Deterministic hashing prevents forgery
   - Cached proofs can be audited later

3. **Network Security**
   - All inter-node communication via TLS
   - Request signing prevents man-in-the-middle
   - Distributed consensus handles Byzantine nodes

4. **Schema Safety**
   - Memory-mapped cache is read-only during execution
   - Generation counter prevents use-after-free
   - Automatic cleanup on cache corruption

## References

- Consistent Hashing: Karger et al., "Consistent Hashing and Random Trees: Distributed Caching Protocols for Relieving Hot Spots on the World Wide Web"
- Byzantine Fault Tolerance: Castro & Liskov, "Practical Byzantine Fault Tolerance"
- Memory-Mapped Files: Bovet & Cesati, "Understanding the Linux Kernel"
- Quorum-Based Consensus: Gifford, "Weighted Voting for Replicated Data"
