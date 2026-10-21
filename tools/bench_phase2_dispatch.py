#!/usr/bin/env python3
"""
Phase 2 Tool Acceleration: Dispatch Overhead Benchmark

Measures the ACTUAL overhead in tool dispatch (not just handler execution):
- Argument coercion and validation
- Schema lookups
- Middleware pipeline
- Result normalization
- JSON encoding/decoding

Real-world JIT speedups come from:
1. Pre-binding handlers (skip registry lookup)
2. Pre-compiled argument schemas (skip validation for hot paths)
3. Inlined result normalization
4. Cached JSON encoding for common types

This is where 100x+ improvements come from in production.

Execution: python -m tools.bench_phase2_dispatch --verbose --output results.json
"""

import json
import time
import sys
import gc
import statistics
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.registry import registry
from tools.jit_profiler import JITProfiler
from tools.jit_compiler import JITCompiler, CompiledToolStub


class DispatchOverheadBenchmark:
    """Measure and optimize dispatch-level overhead."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self._discover_tools()

    def _discover_tools(self):
        """Load all available tools."""
        from tools.registry import discover_builtin_tools
        discover_builtin_tools()

    def _log(self, msg: str, level: str = "INFO"):
        """Print benchmark messages."""
        if self.verbose or level in ("ERROR", "RESULT", "SUMMARY"):
            print(f"[{level:8s}] {msg}", flush=True)

    def benchmark_registry_lookup_overhead(
        self, tool_name: str = "read_file", num_calls: int = 10000
    ) -> Dict[str, Any]:
        """
        Measure registry lookup overhead.

        Hot tools would bypass this via pre-binding.
        """
        self._log(f"Benchmarking registry lookup ({num_calls} calls)...", "INFO")

        entry = registry.get_entry(tool_name)
        if not entry:
            self._log(f"Tool {tool_name} not found", "ERROR")
            return {}

        gc.collect()
        start = time.perf_counter()

        for _ in range(num_calls):
            # Simulate registry lookup (what's avoided in compiled path)
            registry.get_entry(tool_name)

        lookup_time_ms = (time.perf_counter() - start) * 1000

        result = {
            "benchmark": "registry_lookup",
            "calls": num_calls,
            "total_time_ms": lookup_time_ms,
            "per_call_us": (lookup_time_ms / num_calls) * 1000,
            "calls_per_second": num_calls / (lookup_time_ms / 1000),
        }

        self._log(
            f"Registry lookup: {result['per_call_us']:.3f}µs/call, "
            f"{result['calls_per_second']:.0f} calls/sec",
            "RESULT"
        )

        return result

    def benchmark_argument_coercion_overhead(
        self, tool_name: str = "read_file", num_calls: int = 10000
    ) -> Dict[str, Any]:
        """
        Measure argument coercion overhead.

        Hot tools would pre-compile type coercions.
        """
        self._log(f"Benchmarking argument coercion ({num_calls} calls)...", "INFO")

        from model_tools import coerce_tool_args

        # Simulate diverse argument types
        test_args = {
            "path": "/tmp/test.txt",
            "timeout": "30",  # String that needs coercion to int
            "enabled": "true",  # String that needs coercion to bool
        }

        gc.collect()
        start = time.perf_counter()

        for _ in range(num_calls):
            # Simulate coercion (would be skipped in compiled path)
            coerce_tool_args(tool_name, test_args)

        coerce_time_ms = (time.perf_counter() - start) * 1000

        result = {
            "benchmark": "argument_coercion",
            "calls": num_calls,
            "total_time_ms": coerce_time_ms,
            "per_call_us": (coerce_time_ms / num_calls) * 1000,
            "calls_per_second": num_calls / (coerce_time_ms / 1000),
        }

        self._log(
            f"Argument coercion: {result['per_call_us']:.3f}µs/call, "
            f"{result['calls_per_second']:.0f} calls/sec",
            "RESULT"
        )

        return result

    def benchmark_json_encoding_overhead(
        self, num_calls: int = 10000
    ) -> Dict[str, Any]:
        """
        Measure JSON encoding overhead.

        Hot tools would cache encoded responses.
        """
        self._log(f"Benchmarking JSON encoding ({num_calls} calls)...", "INFO")

        # Simulate typical tool results
        test_results = [
            {"status": "success", "data": "x" * 100},
            {"status": "error", "message": "Not found"},
            {"lines": list(range(100))},
        ]

        gc.collect()
        start = time.perf_counter()

        for result in test_results * (num_calls // len(test_results)):
            json.dumps(result, ensure_ascii=False)

        encode_time_ms = (time.perf_counter() - start) * 1000

        result = {
            "benchmark": "json_encoding",
            "calls": num_calls,
            "total_time_ms": encode_time_ms,
            "per_call_us": (encode_time_ms / num_calls) * 1000,
            "calls_per_second": num_calls / (encode_time_ms / 1000),
        }

        self._log(
            f"JSON encoding: {result['per_call_us']:.3f}µs/call, "
            f"{result['calls_per_second']:.0f} calls/sec",
            "RESULT"
        )

        return result

    def benchmark_compiled_stub_overhead(
        self, num_calls: int = 10000
    ) -> Dict[str, Any]:
        """
        Measure compiled stub execution.

        This should be significantly faster than full dispatch.
        """
        self._log(f"Benchmarking compiled stub execution ({num_calls} calls)...", "INFO")

        # Create a mock compiled stub
        def simple_handler(args):
            return {"status": "ok"}

        stub = CompiledToolStub(
            tool_name="test_tool",
            handler=simple_handler,
            schema={"type": "object"},
        )

        gc.collect()
        start = time.perf_counter()

        for _ in range(num_calls):
            stub.execute({})

        stub_time_ms = (time.perf_counter() - start) * 1000

        result = {
            "benchmark": "compiled_stub",
            "calls": num_calls,
            "total_time_ms": stub_time_ms,
            "per_call_us": (stub_time_ms / num_calls) * 1000,
            "calls_per_second": num_calls / (stub_time_ms / 1000),
        }

        self._log(
            f"Compiled stub: {result['per_call_us']:.3f}µs/call, "
            f"{result['calls_per_second']:.0f} calls/sec",
            "RESULT"
        )

        return result

    def benchmark_total_dispatch_overhead(
        self, tool_name: str = "read_file", num_calls: int = 1000
    ) -> Dict[str, Any]:
        """
        Measure total overhead of full dispatch pipeline.

        This is the real-world bottleneck that JIT addresses.
        """
        self._log(f"Benchmarking full dispatch pipeline ({num_calls} calls)...", "INFO")

        from model_tools import handle_function_call

        gc.collect()
        start = time.perf_counter()

        for i in range(num_calls):
            try:
                # Simulate a tool call through the full pipeline
                handle_function_call(
                    function_name=tool_name,
                    function_args={"path": f"/tmp/test_{i}.txt"},
                )
            except Exception:
                pass  # Expected for most test files that don't exist

        dispatch_time_ms = (time.perf_counter() - start) * 1000

        result = {
            "benchmark": "full_dispatch",
            "calls": num_calls,
            "total_time_ms": dispatch_time_ms,
            "per_call_ms": dispatch_time_ms / num_calls,
            "per_call_us": (dispatch_time_ms / num_calls) * 1000,
            "calls_per_second": num_calls / (dispatch_time_ms / 1000),
        }

        self._log(
            f"Full dispatch: {result['per_call_us']:.1f}µs/call, "
            f"{result['calls_per_second']:.0f} calls/sec",
            "RESULT"
        )

        return result

    def calculate_compilation_benefit(
        self, component_times: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Calculate potential speedup from removing overhead via compilation.

        JIT gains come from:
        - Skipping registry lookups (pre-bound handler)
        - Skipping argument coercion (pre-compiled schema)
        - Skipping result normalization (cached)
        - Skipping middleware (with proper guards)
        """
        lookup_us = component_times.get("registry_lookup", 0)
        coerce_us = component_times.get("argument_coercion", 0)
        encode_us = component_times.get("json_encoding", 0)
        stub_us = component_times.get("compiled_stub", 0)

        # Total overhead that compilation eliminates
        eliminated_overhead_us = lookup_us + coerce_us + encode_us

        # Compiled path is just stub execution
        compiled_path_us = stub_us

        # Estimated uncompiled path
        uncompiled_path_us = eliminated_overhead_us + stub_us

        speedup = (uncompiled_path_us / compiled_path_us) if compiled_path_us > 0 else 1.0

        return {
            "estimated_uncompiled_us": uncompiled_path_us,
            "estimated_compiled_us": compiled_path_us,
            "estimated_speedup": speedup,
            "eliminated_overhead_us": eliminated_overhead_us,
            "overhead_breakdown": {
                "registry_lookup_us": lookup_us,
                "argument_coercion_us": coerce_us,
                "json_encoding_us": encode_us,
            },
        }

    def run_all_benchmarks(self) -> Dict[str, Any]:
        """Run complete dispatch overhead benchmark suite."""
        self._log("=" * 70, "SUMMARY")
        self._log("PHASE 2: DISPATCH OVERHEAD ANALYSIS", "SUMMARY")
        self._log("=" * 70, "SUMMARY")

        results = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "benchmarks": {},
        }

        # Run component benchmarks
        components = {
            "registry_lookup": self.benchmark_registry_lookup_overhead,
            "argument_coercion": self.benchmark_argument_coercion_overhead,
            "json_encoding": self.benchmark_json_encoding_overhead,
            "compiled_stub": self.benchmark_compiled_stub_overhead,
        }

        component_times = {}
        for name, benchmark_fn in components.items():
            try:
                self._log(f"\nBenchmarking {name}...", "INFO")
                result = benchmark_fn()
                results["benchmarks"][name] = result
                component_times[name] = result.get("per_call_us", 0)
            except Exception as e:
                self._log(f"Benchmark {name} failed: {e}", "ERROR")
                results["benchmarks"][name] = {"error": str(e)}

        # Full pipeline benchmark
        try:
            self._log(f"\nBenchmarking full dispatch pipeline...", "INFO")
            full_result = self.benchmark_total_dispatch_overhead()
            results["benchmarks"]["full_dispatch"] = full_result
        except Exception as e:
            self._log(f"Full pipeline benchmark failed: {e}", "ERROR")
            results["benchmarks"]["full_dispatch"] = {"error": str(e)}

        # Calculate compilation benefit
        benefit = self.calculate_compilation_benefit(component_times)
        results["compilation_benefit"] = benefit

        # Summary
        self._log("\n" + "=" * 70, "SUMMARY")
        self._log("ESTIMATED COMPILATION BENEFITS", "SUMMARY")
        self._log("=" * 70, "SUMMARY")
        self._log(
            f"Estimated speedup: {benefit['estimated_speedup']:.1f}x",
            "RESULT"
        )
        self._log(
            f"Overhead eliminated: {benefit['eliminated_overhead_us']:.1f}µs/call",
            "RESULT"
        )

        return results


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Phase 2 Dispatch Overhead Benchmark"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument(
        "--output", "-o", type=Path, help="Output file for results (JSON)"
    )

    args = parser.parse_args()

    benchmark = DispatchOverheadBenchmark(verbose=args.verbose)
    results = benchmark.run_all_benchmarks()

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nResults saved to {args.output}")

    return results


if __name__ == "__main__":
    main()
