# Network Layer Optimization for Distributed Tool Dispatch

## Overview

This document describes the comprehensive network layer optimization infrastructure for Hercules distributed tool dispatch. The implementation targets **sub-100µs RPC latency** and **1M+ ops/sec throughput** through a layered architecture combining gRPC, QUIC, compression, multiplexing, and zero-copy serialization.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Tool Call Dispatcher                      │
│          (delegate_tool.py, distributed_dispatch.py)        │
└────────────────┬────────────────────────────────────────────┘
                 │
┌────────────────┴────────────────────────────────────────────┐
│                  Network Layer Abstraction                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  gRPC Tool RPC Layer (grpc_tool_dispatch.py)         │  │
│  │  • Unary RPC: 10-20µs                                │  │
│  │  • Server streaming: 5µs per call                    │  │
│  │  • Bidirectional streaming: continuous dispatch     │  │
│  └──────────────────────────────────────────────────────┘  │
│                          ↓                                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  QUIC Transport Layer (quic_transport.py)            │  │
│  │  • 0-RTT resumption: 2µs                             │  │
│  │  • Connection migration: mobility support           │  │
│  │  • UDP-based: lower latency than TCP                │  │
│  └──────────────────────────────────────────────────────┘  │
│                          ↓                                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Compression Layer (rpc_compression.py)              │  │
│  │  • HPACK-style header compression                    │  │
│  │  • Schema caching: 90% reduction                     │  │
│  │  • Argument deduplication: delta encoding            │  │
│  └──────────────────────────────────────────────────────┘  │
│                          ↓                                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  HTTP/2 Multiplexing (tool_connection_pool.py)       │  │
│  │  • Single connection per node                        │  │
│  │  • Stream multiplexing: 100+ concurrent streams      │  │
│  │  • 100x connection reduction                         │  │
│  └──────────────────────────────────────────────────────┘  │
│                          ↓                                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Zero-Copy Serialization (zerocopy_rpc.py)           │  │
│  │  • Memory-mapped buffers                             │  │
│  │  • Shared memory rings for high-frequency calls      │  │
│  │  • 90% serialization overhead reduction              │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
```

## Components

### 1. gRPC Tool RPC (`grpc_tool_dispatch.py`)

**Purpose**: Ultra-low-latency RPC for distributed tool calls using Protocol Buffers.

**Key Classes**:
- `ProtobufEncoder`: Lightweight Protocol Buffer encoder without external dependencies
- `GrpcChannel`: Represents a gRPC channel to a remote node
- `GrpcDispatcher`: Manages channels and provides unary/streaming interfaces

**Latency Targets**:
- **Unary RPC**: 10-20µs
- **Batched RPC**: 5µs per call
- **Server streaming**: ~6µs per call

**Features**:
- Automatic connection pooling and reconnection
- Exponential backoff on failures
- Health scoring for load balancing
- Per-node latency tracking and p99 percentiles

**Integration Points**:
```python
# In delegate_tool.py or distributed_dispatch.py
from tools.grpc_tool_dispatch import GrpcDispatcher

dispatcher = GrpcDispatcher(max_concurrent_calls=1000)
await dispatcher.add_node("node-1", "10.0.0.1", 9001)

# Unary call
result = await dispatcher.call_best_node("tool_name", "call_id", args)

# Batch calls
calls = [("tool1", "call1", args1), ("tool2", "call2", args2)]
results = await dispatcher.batch_call("node-1", calls)
```

### 2. QUIC Transport (`quic_transport.py`)

**Purpose**: UDP-based transport with 0-RTT resumption and connection migration.

**Key Classes**:
- `QuicConnection`: Represents a QUIC connection to a remote node
- `QuicPacket`: QUIC packet representation
- `QuicTransport`: Manages connection pool with automatic 0-RTT

**Latency Targets**:
- **Handshake**: 25µs (vs 50µs TCP)
- **0-RTT resumption**: 2-5µs
- **Overall improvement**: 10-20% vs TCP-based gRPC

**Features**:
- Automatic 0-RTT resumption with pre-shared keys
- Connection migration for mobility
- Per-connection RTT tracking
- Automatic connection reuse

**Integration Points**:
```python
from tools.quic_transport import QuicTransport

quic = QuicTransport(enable_0rtt=True)

# Gets connection (automatically resuming with 0-RTT if available)
conn = await quic.get_connection("node-1", "10.0.0.1", 9001)

# Send stream data
result = await conn.send_stream_data(stream_id=0, data=b"tool_call_data")

# Or batch
results = await quic.send_batch("node-1", "10.0.0.1", 9001, calls)
```

### 3. Compression Layer (`rpc_compression.py`)

**Purpose**: Reduce payload sizes through header compression and schema caching.

**Key Classes**:
- `HpackEncoder`: HPACK-style header compression
- `SchemaCache`: Tool schema caching with compression metadata
- `ArgumentCompressor`: Delta encoding and pattern matching for arguments
- `RpcCompressionLayer`: Unified compression interface

**Reduction Targets**:
- **Schema references**: 95% reduction vs full schema transmission
- **Repeated arguments**: 90% reduction through delta encoding
- **Overall payload**: 70-90% reduction for repeated calls

**Features**:
- Static and dynamic HPACK tables for header compression
- LRU-based schema cache with deduplication
- Pattern-based argument compression with delta encoding
- Compression ratio tracking and statistics

**Integration Points**:
```python
from tools.rpc_compression import RpcCompressionLayer

compression = RpcCompressionLayer()

# Compress a complete tool call
schema = {"param": "type"}
compressed, metadata = compression.compress_call(
    "tool_name", "call_id", args, schema
)

# Send compressed data to remote

# Decompress on receiver
tool_name, call_id, args = compression.decompress_call(compressed, metadata)
```

### 4. HTTP/2 Multiplexing (`tool_connection_pool.py`)

**Purpose**: Single persistent connection per node with multiplexed streams.

**Key Classes**:
- `Http2Connection`: HTTP/2 connection with stream management
- `StreamState`: Per-stream state and flow control
- `ConnectionPool`: Manages pool of HTTP/2 connections
- `StreamPriority`: Stream prioritization enum

**Connection Reduction**:
- **Before**: N requests × M nodes = N×M connections
- **After**: M nodes × 1-5 connections = M×5 connections
- **Improvement**: 100x reduction in connection count

**Features**:
- Persistent connections across tool calls
- Concurrent stream support (100+ per connection)
- Flow control windows per stream
- PING/latency monitoring
- Automatic connection recycling

**Integration Points**:
```python
from tools.tool_connection_pool import ConnectionPool

pool = ConnectionPool(pool_size=10, max_connections_per_node=5)

# Gets from pool (reuses existing connections)
conn = await pool.get_connection("node-1", "10.0.0.1", 9001)

# Open stream and send data
stream_id = await conn.open_stream()
await conn.send_data(stream_id, b"tool_call_data")
result = await conn.receive_data(stream_id)

# Connection automatically stays in pool for reuse
```

### 5. Zero-Copy Serialization (`zerocopy_rpc.py`)

**Purpose**: Eliminate serialization overhead through shared memory and references.

**Key Classes**:
- `ZeroCopyBuffer`: Buffer supporting zero-copy operations
- `SharedMemoryPool`: Pool of shared memory rings
- `ZeroCopyEncoder`: Encodes RPC messages with zero-copy semantics
- `ZeroCopyDispatcher`: Dispatcher with zero-copy optimization

**Serialization Reduction**:
- **Inline values**: <1µs (memoryview only)
- **Shared memory references**: ~2µs (lookup + validation)
- **Overall overhead reduction**: 90% for large payloads

**Features**:
- Memory-mapped buffer support
- Shared memory rings for high-frequency calls
- Reference-based argument passing (avoid copies)
- Copy-on-write semantics for results
- Automatic garbage collection

**Integration Points**:
```python
from tools.zerocopy_rpc import ZeroCopyDispatcher

dispatcher = ZeroCopyDispatcher()

# Automatically uses zero-copy for large payloads
result = await dispatcher.dispatch_call("tool", "call_id", args)

# Get statistics on zero-copy usage
stats = dispatcher.get_stats()
print(f"Zero-copy calls: {stats['zero_copy_calls']}")
print(f"Bytes saved: {stats['bytes_saved']}")
```

## Integration Guide

### Option 1: Drop-in Replacement for `distributed_dispatch.py`

Replace the existing dispatch logic:

```python
# In run_agent.py or delegate_tool.py
from tools.grpc_tool_dispatch import GrpcDispatcher
from tools.rpc_compression import RpcCompressionLayer
from tools.tool_connection_pool import ConnectionPool

class OptimizedDispatcher:
    def __init__(self):
        self.grpc = GrpcDispatcher()
        self.compression = RpcCompressionLayer()
        self.pool = ConnectionPool()
    
    async def dispatch_tool(self, tool_name, call_id, args):
        # Compress arguments
        compressed, metadata = self.compression.compress_call(
            tool_name, call_id, args
        )
        
        # Route to best node
        node_id = self._select_node()
        
        # Use gRPC for RPC
        result = await self.grpc.call_best_node(
            tool_name, call_id, args
        )
        
        return result
```

### Option 2: Layer on Top of Existing `distributed_dispatch.py`

Keep existing dispatcher and add network optimization:

```python
# In delegate_tool.py
from tools.distributed_dispatch import DistributedDispatcher
from tools.quic_transport import QuicTransport
from tools.zerocopy_rpc import ZeroCopyDispatcher

class NetworkOptimizedDelegation:
    def __init__(self):
        self.dispatcher = DistributedDispatcher()
        self.quic = QuicTransport()
        self.zerocopy = ZeroCopyDispatcher()
    
    async def delegate_task(self, task, toolset_names=None, **kwargs):
        # Use existing dispatcher logic
        result = await self.dispatcher.dispatch(task)
        
        # Apply network optimization
        if should_optimize(task):
            result = await self.zerocopy.dispatch_call(
                task.tool_name, task.call_id, task.args
            )
        
        return result
```

### Option 3: Gradual Migration

Enable network layer optimization incrementally:

```python
# In config.yaml
network_optimization:
  enabled: true
  layers:
    - grpc           # Enable gRPC
    - quic           # Enable QUIC (optional)
    - compression    # Enable compression (recommended)
    - multiplexing   # Enable HTTP/2 multiplexing
    - zerocopy       # Enable zero-copy (for large payloads)
  
  grpc:
    max_concurrent_calls: 1000
  
  compression:
    schema_cache_size: 10000
    enable_delta_encoding: true
  
  pool:
    max_connections_per_node: 5
    idle_timeout_s: 300
```

## Performance Targets

### Latency Breakdown (End-to-End)

For a typical tool call with 1KB arguments:

```
Total: ~50-100µs

├─ Compression layer:      5-10µs
│  ├─ Schema lookup:        1µs
│  └─ Argument encoding:    4-9µs
│
├─ Network transmission:   20-30µs (includes serialization)
│  ├─ Protobuf encoding:    2-5µs
│  ├─ QUIC/TCP transport:   5-10µs
│  └─ Remote transmission:  10-20µs
│
├─ Remote execution:      20-50µs (tool-dependent)
│
└─ Result transmission:    5-10µs
```

### Throughput Targets

For a 3-node cluster with optimal configuration:

```
Mode                    Throughput      Per-node
─────────────────────────────────────────────────
Unary RPC               300k calls/sec  ~100k calls/sec
Batched (50 calls)      1M+ calls/sec   ~330k calls/sec
Streaming               500k calls/sec  ~166k calls/sec
```

### Memory Efficiency

```
Baseline (per node):
  • HTTP connections: 10GB (1000 connections × 10MB)
  • Connection metadata: 100MB
  Total: ~10.1GB

Optimized:
  • HTTP/2 connections: 100MB (5 connections × 20MB)
  • Schema cache: 100MB
  • Shared memory pool: 256MB
  Total: ~456MB

Reduction: ~95% memory savings
```

## Benchmarking

Run the comprehensive benchmark suite:

```bash
# Run all benchmarks
python -m tools.bench_network_layer --num-calls 10000 --verbose

# Profile with detailed metrics
python -m tools.bench_network_layer --profile --verbose --num-calls 5000

# Save results
python -m tools.bench_network_layer > bench_results.txt
```

**Benchmark Modules**:
1. **Protobuf Encoding** - Measures serialization speed (~3-10µs)
2. **gRPC RPC** - Unary and batch latency tests
3. **QUIC Transport** - Handshake and 0-RTT resumption
4. **Compression** - Schema cache hit rates and compression ratios
5. **HTTP/2 Multiplexing** - Stream and connection overhead
6. **Zero-Copy Serialization** - Memory efficiency and reference overhead
7. **End-to-End** - Full integration with all layers

## Monitoring and Observability

### Metrics to Track

```python
# In agent/task_aware_model_router.py or monitoring dashboard
network_metrics = {
    "rpc_latency_p50": 15.0,       # µs
    "rpc_latency_p99": 45.0,       # µs
    "rpc_latency_p999": 95.0,      # µs
    
    "throughput": 250_000,         # calls/sec
    "success_rate": 0.9995,        # 99.95%
    
    "compression_ratio": 0.15,     # 85% reduction
    "schema_cache_hit_rate": 0.92, # 92% hits
    
    "zero_copy_ratio": 0.65,       # 65% of calls use zero-copy
    "bytes_saved": 1_234_567_890,  # bytes
    
    "connections": 15,             # total open connections
    "streams": 342,                # concurrent streams
    "pool_reuse_rate": 0.98,       # 98% connection reuse
}
```

### Logging Integration

```python
logger = logging.getLogger("hercules.network")

# Log slow RPC calls
logger.warning(f"Slow RPC: {tool_name} took {latency_us:.1f}µs (p99: {p99_us:.1f}µs)")

# Log compression efficiency
logger.info(f"Schema cache: {hit_rate:.1%} hit rate, {schema_count} schemas cached")

# Log connection pool status
logger.debug(f"Connection pool: {open_conns}/{max_conns} open, {stream_count} streams")
```

## Troubleshooting

### High RPC Latency

1. Check gRPC channel health scores:
   ```python
   stats = dispatcher.get_stats()
   for node_id, metrics in stats['nodes'].items():
       if metrics['health_score'] < 0.8:
           logger.warning(f"{node_id} health: {metrics['health_score']}")
   ```

2. Check network layer statistics:
   ```python
   compression_stats = compression.get_stats()
   if compression_stats['schema_cache']['hit_rate'] < 0.5:
       logger.warning("Low schema cache hit rate - may need larger cache")
   ```

3. Verify QUIC resumption is working:
   ```python
   quic_stats = quic.get_stats()
   if quic_stats['resumptions'] < quic_stats['handshakes'] * 0.7:
       logger.warning("Low 0-RTT resumption rate")
   ```

### High Memory Usage

1. Reduce schema cache size:
   ```python
   schema_cache = SchemaCache(max_entries=1000)  # Default: 10000
   ```

2. Reduce shared memory pool:
   ```python
   zerocopy = ZeroCopyDispatcher()
   zerocopy.shared_mem_pool = SharedMemoryPool(ring_size=256*1024, num_rings=2)
   ```

3. Monitor connection pool:
   ```python
   pool_stats = pool.get_stats()
   logger.info(f"Connections: {pool_stats['total_open_connections']}")
   ```

### Low Compression Ratio

1. Check argument patterns:
   ```python
   arg_stats = compressor.get_stats()
   if arg_stats['compressions'] == 0:
       # No compression happening - arguments may be too diverse
       logger.warning("Argument compression inactive")
   ```

2. Enable delta encoding:
   ```python
   # Already enabled by default in ArgumentCompressor
   compressor = ArgumentCompressor(max_patterns=5000)
   ```

## Future Optimizations

1. **Kernel-Space RPC**: eBPF-based in-kernel RPC (5-10µs)
2. **RDMA Support**: Remote Direct Memory Access for ultra-low latency
3. **Hardware Acceleration**: TCP offload engines (TOE) for network stack
4. **Intelligent Batching**: ML-driven batch sizing based on load
5. **Adaptive Compression**: Dynamic codec selection per call pattern

## References

- QUIC RFC 9000: https://tools.ietf.org/html/rfc9000
- HTTP/2 RFC 7540: https://tools.ietf.org/html/rfc7540
- HPACK RFC 7541: https://tools.ietf.org/html/rfc7541
- gRPC: https://grpc.io/docs/what-is-grpc/
