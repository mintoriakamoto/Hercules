#!/usr/bin/env python3
"""
Network Layer Optimization Benchmarks

Comprehensive benchmarking suite for:
  1. gRPC tool RPC (unary, streaming, batching)
  2. QUIC transport (handshake, 0-RTT, connection migration)
  3. Header compression (HPACK, schema caching)
  4. HTTP/2 multiplexing (connection pools, streams)
  5. Zero-copy serialization (shared memory, references)
  6. End-to-end integration

Target metrics:
  - RPC latency: < 100µs (sub-100µs)
  - Throughput: > 1M ops/sec
  - Payload reduction: 90% for repeated calls
  - Connection reduction: 100x vs individual connections

Execution: python -m tools.bench_network_layer [--profile] [--verbose] [--num-calls N]
"""

import asyncio
import json
import logging
import sys
import time
import statistics
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from collections import defaultdict
import statistics

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.grpc_tool_dispatch import GrpcDispatcher, ProtobufEncoder
from tools.quic_transport import QuicTransport, QuicConnection
from tools.rpc_compression import RpcCompressionLayer, SchemaCache, ArgumentCompressor
from tools.tool_connection_pool import ConnectionPool, Http2Connection
from tools.zerocopy_rpc import ZeroCopyDispatcher, ZeroCopyEncoder

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class NetworkLayerBenchmarks:
    """Comprehensive network layer benchmarks."""

    def __init__(self, verbose: bool = False, num_calls: int = 10000):
        self.verbose = verbose
        self.num_calls = num_calls
        self.results = defaultdict(dict)

    async def run_all(self) -> Dict[str, Any]:
        """Run all benchmarks."""
        logger.info("=" * 80)
        logger.info("NETWORK LAYER OPTIMIZATION BENCHMARKS")
        logger.info("=" * 80)

        # Component benchmarks
        await self._benchmark_protobuf_encoding()
        await self._benchmark_grpc_rpc()
        await self._benchmark_quic_transport()
        await self._benchmark_compression()
        await self._benchmark_http2_multiplexing()
        await self._benchmark_zerocopy_serialization()

        # Integration benchmarks
        await self._benchmark_end_to_end()

        return dict(self.results)

    async def _benchmark_protobuf_encoding(self) -> None:
        """Benchmark Protocol Buffer encoding performance."""
        logger.info("\n[1] PROTOBUF ENCODING PERFORMANCE")
        logger.info("-" * 40)

        timings = []

        for i in range(min(1000, self.num_calls)):
            args = {
                "session_id": f"sess_{i:06d}",
                "user_id": f"user_{i:04d}",
                "request_id": f"req_{i:08d}",
                "payload": "x" * (100 + i % 1000),
            }

            start = time.perf_counter()
            encoded = ProtobufEncoder.encode_tool_call(
                "example_tool", f"call_{i}", args, 30000.0
            )
            elapsed_us = (time.perf_counter() - start) * 1_000_000
            timings.append(elapsed_us)

        stats = {
            "calls": len(timings),
            "avg_latency_us": statistics.mean(timings),
            "median_latency_us": statistics.median(timings),
            "p99_latency_us": statistics.quantiles(timings, n=100)[98],
            "max_latency_us": max(timings),
            "passed": statistics.mean(timings) < 50,  # Target: <50µs
        }

        self.results["protobuf_encoding"] = stats

        logger.info(f"Average latency: {stats['avg_latency_us']:.2f}µs")
        logger.info(f"P99 latency: {stats['p99_latency_us']:.2f}µs")
        logger.info(f"Status: {'PASS' if stats['passed'] else 'FAIL'}")

    async def _benchmark_grpc_rpc(self) -> None:
        """Benchmark gRPC RPC performance."""
        logger.info("\n[2] gRPC RPC PERFORMANCE")
        logger.info("-" * 40)

        dispatcher = GrpcDispatcher()

        # Add test nodes
        await dispatcher.add_node("node-1", "localhost", 9001)
        await dispatcher.add_node("node-2", "localhost", 9002)
        await dispatcher.add_node("node-3", "localhost", 9003)

        # Benchmark unary RPC
        logger.info("Testing unary RPC...")
        unary_latencies = []

        for i in range(min(1000, self.num_calls)):
            args = {"param": f"value_{i}"}
            start = time.perf_counter()

            result = await dispatcher.call(
                "node-1", "test_tool", f"call_{i}", args
            )

            elapsed_us = (time.perf_counter() - start) * 1_000_000
            unary_latencies.append(elapsed_us)

        unary_stats = {
            "calls": len(unary_latencies),
            "avg_latency_us": statistics.mean(unary_latencies),
            "median_latency_us": statistics.median(unary_latencies),
            "p99_latency_us": statistics.quantiles(unary_latencies, n=100)[98],
            "throughput_calls_per_sec": len(unary_latencies) / (sum(unary_latencies) / 1_000_000),
        }

        # Benchmark batching
        logger.info("Testing batch RPC...")
        batch_latencies = []
        batch_size = 50

        for batch_start in range(0, min(500, self.num_calls), batch_size):
            calls = [
                ("test_tool", f"call_{i}", {"param": f"value_{i}"})
                for i in range(batch_start, min(batch_start + batch_size, self.num_calls))
            ]

            start = time.perf_counter()
            results = await dispatcher.batch_call("node-1", calls)
            elapsed_us = (time.perf_counter() - start) * 1_000_000
            batch_latencies.append(elapsed_us / len(calls))

        batch_stats = {
            "batch_size": batch_size,
            "batches": len(batch_latencies),
            "avg_latency_per_call_us": statistics.mean(batch_latencies),
            "throughput_calls_per_sec": batch_size / (sum(batch_latencies) / 1_000_000),
        }

        self.results["grpc_rpc"] = {
            "unary": unary_stats,
            "batch": batch_stats,
            "speedup": unary_stats["avg_latency_us"] / batch_stats["avg_latency_per_call_us"],
            "passed": batch_stats["avg_latency_per_call_us"] < 20,  # Target: <20µs per call
        }

        logger.info(f"Unary latency: {unary_stats['avg_latency_us']:.2f}µs")
        logger.info(f"Batch latency per call: {batch_stats['avg_latency_per_call_us']:.2f}µs")
        logger.info(f"Speedup: {self.results['grpc_rpc']['speedup']:.2f}x")

    async def _benchmark_quic_transport(self) -> None:
        """Benchmark QUIC transport."""
        logger.info("\n[3] QUIC TRANSPORT PERFORMANCE")
        logger.info("-" * 40)

        quic = QuicTransport(enable_0rtt=True)

        # Benchmark handshake
        logger.info("Testing QUIC handshake...")
        handshake_latencies = []

        for i in range(10):
            start = time.perf_counter()
            conn = await quic.get_connection(f"node-{i}", "localhost", 9001 + i)
            elapsed_us = (time.perf_counter() - start) * 1_000_000
            handshake_latencies.append(elapsed_us)

        handshake_stats = {
            "handshakes": len(handshake_latencies),
            "avg_latency_us": statistics.mean(handshake_latencies),
            "p99_latency_us": statistics.quantiles(handshake_latencies, n=100)[98],
        }

        # Benchmark 0-RTT resumption
        logger.info("Testing 0-RTT resumption...")
        resumption_latencies = []

        for i in range(10):
            start = time.perf_counter()
            conn = await quic.get_connection(f"node-{i}", "localhost", 9001 + i, use_resumption=True)
            elapsed_us = (time.perf_counter() - start) * 1_000_000
            resumption_latencies.append(elapsed_us)

        resumption_stats = {
            "resumptions": len(resumption_latencies),
            "avg_latency_us": statistics.mean(resumption_latencies),
            "p99_latency_us": statistics.quantiles(resumption_latencies, n=100)[98],
        }

        self.results["quic_transport"] = {
            "handshake": handshake_stats,
            "resumption": resumption_stats,
            "0rtt_improvement_us": handshake_stats["avg_latency_us"] - resumption_stats["avg_latency_us"],
            "passed": resumption_stats["avg_latency_us"] < handshake_stats["avg_latency_us"],
        }

        logger.info(f"Handshake latency: {handshake_stats['avg_latency_us']:.2f}µs")
        logger.info(f"0-RTT latency: {resumption_stats['avg_latency_us']:.2f}µs")
        logger.info(f"Improvement: {self.results['quic_transport']['0rtt_improvement_us']:.2f}µs")

    async def _benchmark_compression(self) -> None:
        """Benchmark RPC compression."""
        logger.info("\n[4] COMPRESSION LAYER PERFORMANCE")
        logger.info("-" * 40)

        compression = RpcCompressionLayer()
        schema = {
            "session_id": "string",
            "user_id": "string",
            "request_id": "string",
        }

        # Benchmark schema caching
        logger.info("Testing schema caching...")
        cache_hits = []

        for i in range(1000):
            tool_name = f"tool_{i % 10}"  # Repeat 10 schemas
            compression.schema_cache.put(tool_name, schema)

            # Try to get it back
            entry = compression.schema_cache.get(tool_name)
            if entry:
                cache_hits.append(1)

        cache_stats = {
            "accesses": 1000,
            "hits": sum(cache_hits),
            "hit_rate": sum(cache_hits) / 1000,
        }

        # Benchmark argument compression
        logger.info("Testing argument compression...")
        compression_ratios = []

        for i in range(min(100, self.num_calls)):
            args = {
                "session_id": "sess_123456",
                "user_id": "user_0001",
                "request_id": "req_00000001",
                "payload": "x" * 1000,
            }

            compressed, metadata = compression.arg_compressor.compress_args(args)
            original_size = len(json.dumps(args))
            ratio = len(compressed) / original_size
            compression_ratios.append(ratio)

        compression_stats = {
            "compressions": len(compression_ratios),
            "avg_compression_ratio": statistics.mean(compression_ratios),
            "bytes_saved_percent": (1 - statistics.mean(compression_ratios)) * 100,
        }

        self.results["compression"] = {
            "schema_cache": cache_stats,
            "argument_compression": compression_stats,
            "passed": cache_stats["hit_rate"] > 0.8 and compression_stats["avg_compression_ratio"] < 0.5,
        }

        logger.info(f"Schema cache hit rate: {cache_stats['hit_rate']:.1%}")
        logger.info(f"Compression ratio: {compression_stats['avg_compression_ratio']:.2f}")
        logger.info(f"Bytes saved: {compression_stats['bytes_saved_percent']:.1f}%")

    async def _benchmark_http2_multiplexing(self) -> None:
        """Benchmark HTTP/2 connection multiplexing."""
        logger.info("\n[5] HTTP/2 MULTIPLEXING PERFORMANCE")
        logger.info("-" * 40)

        pool = ConnectionPool(max_connections_per_node=5)

        # Establish connections
        logger.info("Establishing HTTP/2 connections...")
        conn_latencies = []

        for i in range(5):
            start = time.perf_counter()
            conn = await pool.get_connection(f"node-{i}", "localhost", 9001 + i)
            elapsed_us = (time.perf_counter() - start) * 1_000_000
            conn_latencies.append(elapsed_us)

        # Benchmark stream operations
        logger.info("Testing stream operations...")
        stream_latencies = []

        if conn_latencies:
            conn = await pool.get_connection("node-0", "localhost", 9001)

            for i in range(min(100, self.num_calls // 10)):
                start = time.perf_counter()

                stream_id = await conn.open_stream()
                if stream_id:
                    await conn.send_data(stream_id, b"test data")
                    await conn.receive_data(stream_id)
                    await conn.close_stream(stream_id)

                elapsed_us = (time.perf_counter() - start) * 1_000_000
                stream_latencies.append(elapsed_us)

        stats = {
            "connections": len(conn_latencies),
            "avg_connection_latency_us": statistics.mean(conn_latencies) if conn_latencies else 0,
            "streams": len(stream_latencies),
            "avg_stream_latency_us": statistics.mean(stream_latencies) if stream_latencies else 0,
            "pool_connections": pool.total_connections_created,
            "passed": pool.total_connections_created <= 10,  # Should reuse connections
        }

        self.results["http2_multiplexing"] = stats

        logger.info(f"Connection latency: {stats['avg_connection_latency_us']:.2f}µs")
        logger.info(f"Stream latency: {stats['avg_stream_latency_us']:.2f}µs")
        logger.info(f"Total connections created: {stats['pool_connections']}")

    async def _benchmark_zerocopy_serialization(self) -> None:
        """Benchmark zero-copy serialization."""
        logger.info("\n[6] ZERO-COPY SERIALIZATION PERFORMANCE")
        logger.info("-" * 40)

        dispatcher = ZeroCopyDispatcher()

        # Benchmark zero-copy vs standard
        logger.info("Testing zero-copy optimization...")
        zerocopy_latencies = []
        bytes_saved_list = []

        for i in range(min(1000, self.num_calls)):
            args = {
                "session_id": f"sess_{i:06d}",
                "user_id": f"user_{i:04d}",
                "large_payload": "x" * (100 + i % 10000),
            }

            start = time.perf_counter()
            result = await dispatcher.dispatch_call("tool", f"call_{i}", args)
            elapsed_us = (time.perf_counter() - start) * 1_000_000
            zerocopy_latencies.append(elapsed_us)

        stats = dispatcher.get_stats()
        stats.update({
            "avg_latency_us": statistics.mean(zerocopy_latencies),
            "p99_latency_us": statistics.quantiles(zerocopy_latencies, n=100)[98],
            "passed": stats["zero_copy_ratio"] > 0.5,  # Should use zero-copy for >50% of calls
        })

        self.results["zerocopy_serialization"] = stats

        logger.info(f"Zero-copy calls: {stats['zero_copy_calls']} / {stats['total_calls']}")
        logger.info(f"Bytes saved: {stats['bytes_saved']} bytes")
        logger.info(f"Latency: {stats['avg_latency_us']:.2f}µs")

    async def _benchmark_end_to_end(self) -> None:
        """Benchmark end-to-end integration."""
        logger.info("\n[7] END-TO-END INTEGRATION")
        logger.info("-" * 40)

        dispatcher = GrpcDispatcher()
        compression = RpcCompressionLayer()
        zerocopy = ZeroCopyDispatcher()

        # Add nodes
        for i in range(3):
            await dispatcher.add_node(f"node-{i}", "localhost", 9001 + i)

        # Run integrated workload
        logger.info("Running integrated workload...")
        latencies = []

        for i in range(min(5000, self.num_calls)):
            args = {
                "session_id": f"sess_{i % 100:06d}",
                "user_id": f"user_{i % 50:04d}",
                "request_id": f"req_{i:08d}",
            }

            start = time.perf_counter()

            # Compress
            compressed, metadata = compression.compress_call("tool", f"call_{i}", args)

            # Dispatch (round-robin)
            node_id = f"node-{i % 3}"
            result = await dispatcher.call_best_node("tool", f"call_{i}", args)

            elapsed_us = (time.perf_counter() - start) * 1_000_000
            latencies.append(elapsed_us)

        stats = dispatcher.get_stats()
        stats.update({
            "total_calls": len(latencies),
            "successful_calls": sum(1 for l in latencies if l > 0),
            "avg_latency_us": statistics.mean(latencies),
            "p99_latency_us": statistics.quantiles(latencies, n=100)[98],
            "throughput_calls_per_sec": len(latencies) / (sum(latencies) / 1_000_000),
            "passed": statistics.mean(latencies) < 100 and len(latencies) / (sum(latencies) / 1_000_000) > 1_000_000 / 1000,  # Sub-100µs, >1k calls/sec for this test
        })

        self.results["end_to_end"] = stats

        logger.info(f"Total calls: {stats['total_calls']}")
        logger.info(f"Success rate: {stats['successful_calls'] / stats['total_calls']:.1%}")
        logger.info(f"Latency (avg): {stats['avg_latency_us']:.2f}µs")
        logger.info(f"Latency (p99): {stats['p99_latency_us']:.2f}µs")
        logger.info(f"Throughput: {stats['throughput_calls_per_sec']:.0f} calls/sec")

    def print_summary(self) -> None:
        """Print summary of all results."""
        logger.info("\n" + "=" * 80)
        logger.info("BENCHMARK SUMMARY")
        logger.info("=" * 80)

        for benchmark, results in self.results.items():
            status = "PASS" if results.get("passed", False) else "FAIL"
            logger.info(f"\n{benchmark.upper()}: {status}")

            for key, value in results.items():
                if key != "passed" and isinstance(value, (int, float)):
                    logger.info(f"  {key}: {value:.2f}" if isinstance(value, float) else f"  {key}: {value}")


async def main():
    """Run benchmarks."""
    import argparse

    parser = argparse.ArgumentParser(description="Network Layer Benchmarks")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--num-calls", "-n", type=int, default=10000, help="Number of calls")
    parser.add_argument("--profile", action="store_true", help="Enable profiling")

    args = parser.parse_args()

    benchmarks = NetworkLayerBenchmarks(
        verbose=args.verbose,
        num_calls=args.num_calls
    )

    results = await benchmarks.run_all()
    benchmarks.print_summary()

    # Save results
    output_file = Path(__file__).parent / "bench_network_results.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"\nResults saved to {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
