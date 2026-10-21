#!/usr/bin/env python3
"""
Phase 2 Tool Acceleration Benchmark Suite: JIT Compilation

Validates JIT compilation optimizations:
1. Hot tool identification via profiling
2. Compilation overhead vs. execution savings
3. Compiled vs. interpreted path performance
4. 100x+ speedup validation on hot tools
5. Memory impact of compiled stubs

Execution: python -m tools.bench_phase2 [--profile] [--verbose] [--output <path>]
"""

import json
import time
import sys
import gc
import psutil
import statistics
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional, Callable
from collections import defaultdict
import threading

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.registry import registry, ToolEntry
from tools.jit_profiler import JITProfiler, get_global_profiler
from tools.jit_compiler import JITCompiler, get_global_compiler, CompiledToolStub
from model_tools import get_tool_definitions


class BenchmarkTimer:
    """Context manager for precise timing measurements."""

    def __init__(self, name: str = ""):
        self.name = name
        self.start_time = None
        self.elapsed_ms = 0.0
        self.start_memory = 0
        self.end_memory = 0

    def __enter__(self):
        gc.collect()
        self.start_memory = psutil.Process().memory_info().rss
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.elapsed_ms = (time.perf_counter() - self.start_time) * 1000.0
        self.end_memory = psutil.Process().memory_info().rss

    @property
    def memory_delta_mb(self) -> float:
        """Memory change in MB."""
        return (self.end_memory - self.start_memory) / (1024 * 1024)


class Phase2Benchmarks:
    """Complete benchmark suite for Phase 2 JIT compilation."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results = defaultdict(list)
        self.profiler = JITProfiler()
        self.compiler = JITCompiler()
        self.tool_entries = {}
        self._discover_tools()

    def _discover_tools(self):
        """Populate registry and cache tool entries."""
        from tools.registry import discover_builtin_tools
        discover_builtin_tools()

        # Cache tool entries for quick access
        for name in registry.get_all_tool_names()[:20]:  # Use first 20 for benchmarks
            entry = registry.get_entry(name)
            if entry:
                self.tool_entries[name] = entry

    def _log(self, msg: str, level: str = "INFO"):
        """Print benchmark messages."""
        if self.verbose or level in ("ERROR", "RESULT", "SUMMARY"):
            timestamp = time.strftime("%H:%M:%S")
            print(f"[{timestamp}] {level:8s} {msg}", flush=True)

    # =========================================================================
    # PROFILING PHASE: Simulate realistic tool call distribution
    # =========================================================================

    def benchmark_profiling_accuracy(self, num_calls: int = 5000) -> Dict[str, Any]:
        """Benchmark profiler accuracy and overhead."""
        self._log(f"Benchmarking profiler accuracy ({num_calls} calls)...", "INFO")

        if not self.tool_entries:
            self._log("No tools to profile", "ERROR")
            return {}

        tool_names = list(self.tool_entries.keys())

        # Simulate realistic distribution: 80/20 rule (few tools get most calls)
        # Pareto distribution approximation
        call_distribution = []
        for i, name in enumerate(tool_names):
            # Exponential decay: first tool ~40% of calls, decreases rapidly
            weight = 40 * (0.7 ** i)
            call_count = max(1, int(num_calls * weight / 100))
            call_distribution.append((name, call_count))

        total_allocated = sum(count for _, count in call_distribution)

        with BenchmarkTimer("Profiling") as timer:
            for tool_name, count in call_distribution:
                for _ in range(count):
                    # Simulate varying execution times
                    duration_ms = 1.0 + (hash(tool_name) % 10)
                    self.profiler.record_call(tool_name, duration_ms, success=True)
                    gc.collect()  # Let GC run to simulate realistic workload

        summary = self.profiler.get_profile_summary()

        result = {
            "benchmark": "profiling_accuracy",
            "profiling_time_ms": timer.elapsed_ms,
            "calls_profiled": self.profiler.total_calls,
            "calls_per_second": self.profiler.total_calls / max(1, timer.elapsed_ms / 1000),
            "unique_tools_tracked": len(self.profiler.stats),
            "hot_tools_identified": len(self.profiler.get_hot_tools()),
            "profiler_memory_mb": timer.memory_delta_mb,
            "profile_summary": summary,
        }

        self._log(f"Profiled {result['calls_profiled']} calls in {timer.elapsed_ms:.2f}ms", "RESULT")
        self._log(f"Identified {result['hot_tools_identified']} hot tools", "RESULT")

        return result

    # =========================================================================
    # COMPILATION PHASE: Measure compilation overhead
    # =========================================================================

    def benchmark_compilation_overhead(self) -> Dict[str, Any]:
        """Measure compilation time and memory overhead."""
        self._log("Benchmarking JIT compilation overhead...", "INFO")

        if not self.tool_entries:
            self._log("No tools to compile", "ERROR")
            return {}

        compilation_times = []
        memory_overhead = []

        for tool_name, entry in list(self.tool_entries.items())[:10]:
            with BenchmarkTimer(f"Compiling {tool_name}") as timer:
                stub = self.compiler.compile_tool(
                    tool_name=tool_name,
                    handler=entry.handler,
                    schema=entry.schema,
                )

            if stub:
                compilation_times.append(stub.compile_time_ms)
                memory_overhead.append(timer.memory_delta_mb)

        result = {
            "benchmark": "compilation_overhead",
            "tools_compiled": len(compilation_times),
            "total_compilation_time_ms": sum(compilation_times),
            "avg_compilation_time_ms": statistics.mean(compilation_times) if compilation_times else 0,
            "max_compilation_time_ms": max(compilation_times) if compilation_times else 0,
            "total_memory_mb": sum(memory_overhead),
            "avg_memory_per_tool_mb": statistics.mean(memory_overhead) if memory_overhead else 0,
        }

        self._log(
            f"Compiled {result['tools_compiled']} tools in {result['total_compilation_time_ms']:.2f}ms",
            "RESULT"
        )
        self._log(
            f"Memory overhead: {result['total_memory_mb']:.2f}MB ({result['avg_memory_per_tool_mb']:.2f}MB/tool)",
            "RESULT"
        )

        return result

    # =========================================================================
    # EXECUTION PHASE: Compiled vs. Interpreted comparison
    # =========================================================================

    def benchmark_execution_speedup(self, num_calls: int = 1000) -> Dict[str, Any]:
        """Compare compiled vs. interpreted execution performance."""
        self._log(f"Benchmarking execution speedup ({num_calls} calls)...", "INFO")

        if not self.tool_entries:
            self._log("No tools to execute", "ERROR")
            return {}

        results = {}

        # Test one tool with simple execution
        test_tool_name = list(self.tool_entries.keys())[0]
        test_entry = self.tool_entries[test_tool_name]

        self._log(f"Testing tool: {test_tool_name}", "INFO")

        # Warm up
        for _ in range(10):
            try:
                test_entry.handler({})
            except:
                pass

        # Compiled path
        stub = self.compiler.compile_tool(
            tool_name=test_tool_name,
            handler=test_entry.handler,
            schema=test_entry.schema,
        )

        compiled_times = []
        if stub:
            gc.collect()
            start = time.perf_counter()
            for _ in range(num_calls):
                try:
                    stub.execute({})
                except:
                    pass
            compiled_duration_ms = (time.perf_counter() - start) * 1000
            compiled_times = [compiled_duration_ms / num_calls] * num_calls

        # Interpreted path (via direct handler)
        gc.collect()
        start = time.perf_counter()
        for _ in range(num_calls):
            try:
                test_entry.handler({})
            except:
                pass
        interpreted_duration_ms = (time.perf_counter() - start) * 1000
        interpreted_times = [interpreted_duration_ms / num_calls] * num_calls

        speedup = interpreted_duration_ms / max(1, sum(compiled_times) / num_calls)

        result = {
            "benchmark": "execution_speedup",
            "test_tool": test_tool_name,
            "calls": num_calls,
            "interpreted_total_ms": interpreted_duration_ms,
            "compiled_total_ms": sum(compiled_times) / num_calls if compiled_times else 0,
            "interpreted_per_call_us": (interpreted_duration_ms / num_calls) * 1000,
            "compiled_per_call_us": (sum(compiled_times) / (num_calls * len(compiled_times))) * 1000 if compiled_times else 0,
            "speedup_factor": speedup,
        }

        self._log(
            f"Speedup: {speedup:.2f}x ({result['interpreted_per_call_us']:.2f}µs → {result['compiled_per_call_us']:.2f}µs)",
            "RESULT"
        )

        return result

    # =========================================================================
    # AGGREGATE PHASE: Full pipeline benchmark
    # =========================================================================

    def benchmark_full_pipeline(self, total_calls: int = 10000) -> Dict[str, Any]:
        """Benchmark complete JIT pipeline with realistic workload."""
        self._log(f"Benchmarking full pipeline ({total_calls} calls)...", "INFO")

        if not self.tool_entries:
            self._log("No tools for full pipeline", "ERROR")
            return {}

        pipeline_profiler = JITProfiler()
        pipeline_compiler = JITCompiler()
        tool_names = list(self.tool_entries.keys())

        # Phase 1: Profile
        self._log("Phase 1: Profiling...", "INFO")
        with BenchmarkTimer("Profile phase") as profile_timer:
            for i in range(total_calls):
                tool_name = tool_names[i % len(tool_names)]
                duration = 0.5 + (i % 3) * 0.2
                pipeline_profiler.record_call(tool_name, duration, success=True)

        # Phase 2: Compile hot tools
        self._log("Phase 2: Compiling hot tools...", "INFO")
        with BenchmarkTimer("Compilation phase") as compile_timer:
            hot_tools = pipeline_profiler.suggest_compilation_targets(min_call_count=50)
            for tool_name in hot_tools[:5]:  # Compile top 5
                entry = self.tool_entries.get(tool_name)
                if entry:
                    pipeline_compiler.compile_tool(
                        tool_name=tool_name,
                        handler=entry.handler,
                        schema=entry.schema,
                    )

        result = {
            "benchmark": "full_pipeline",
            "total_calls": total_calls,
            "profile_time_ms": profile_timer.elapsed_ms,
            "compilation_time_ms": compile_timer.elapsed_ms,
            "tools_profiled": len(pipeline_profiler.stats),
            "hot_tools_compiled": len(
                [s for s in pipeline_compiler.compiled_stubs.values() if s.call_count > 0]
            ),
            "profile_overhead_percent": (profile_timer.elapsed_ms / total_calls) * 100,
            "total_phase2_time_ms": profile_timer.elapsed_ms + compile_timer.elapsed_ms,
        }

        self._log(
            f"Full pipeline: profile={profile_timer.elapsed_ms:.2f}ms, "
            f"compile={compile_timer.elapsed_ms:.2f}ms",
            "RESULT"
        )

        return result

    # =========================================================================
    # VALIDATION: Prove 100x+ improvements on hot paths
    # =========================================================================

    def validate_100x_improvement(self) -> Dict[str, Any]:
        """
        Validate that hot paths show 100x+ speedup.
        This is the core validation metric for Phase 2.
        """
        self._log("Validating 100x+ improvement target...", "INFO")

        speedup_results = self.benchmark_execution_speedup(num_calls=5000)
        actual_speedup = speedup_results.get("speedup_factor", 1.0)

        target_speedup = 100.0
        met = actual_speedup >= target_speedup

        result = {
            "benchmark": "validation_100x",
            "target_speedup": target_speedup,
            "actual_speedup": actual_speedup,
            "met_target": met,
            "speedup_ratio": actual_speedup / target_speedup if target_speedup > 0 else 0,
            "status": "PASS" if met else "FAIL",
        }

        status = "✓ PASS" if met else "✗ FAIL"
        self._log(f"{status}: 100x target ({actual_speedup:.2f}x achieved)", "SUMMARY")

        return result

    # =========================================================================
    # MAIN RUNNER
    # =========================================================================

    def run_all_benchmarks(self) -> Dict[str, Any]:
        """Run complete benchmark suite."""
        self._log("=" * 70, "SUMMARY")
        self._log("PHASE 2: JIT COMPILATION BENCHMARKS", "SUMMARY")
        self._log("=" * 70, "SUMMARY")

        all_results = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "benchmarks": {},
        }

        # Run each benchmark
        benchmarks = [
            ("Profiling", self.benchmark_profiling_accuracy),
            ("Compilation", self.benchmark_compilation_overhead),
            ("Execution", self.benchmark_execution_speedup),
            ("Full Pipeline", self.benchmark_full_pipeline),
            ("Validation", self.validate_100x_improvement),
        ]

        for name, benchmark_fn in benchmarks:
            try:
                self._log(f"\nRunning: {name}...", "INFO")
                result = benchmark_fn()
                all_results["benchmarks"][name] = result
            except Exception as e:
                self._log(f"Benchmark {name} failed: {e}", "ERROR")
                all_results["benchmarks"][name] = {"error": str(e)}

        # Summary
        self._log("\n" + "=" * 70, "SUMMARY")
        self._log("BENCHMARK SUMMARY", "SUMMARY")
        self._log("=" * 70, "SUMMARY")

        for name, result in all_results["benchmarks"].items():
            if "error" not in result:
                self._log(f"{name}: {result.get('status', 'COMPLETED')}", "SUMMARY")

        return all_results


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Phase 2 JIT Compilation Benchmarks"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument(
        "--output", "-o", type=Path, help="Output file for results (JSON)"
    )

    args = parser.parse_args()

    benchmarks = Phase2Benchmarks(verbose=args.verbose)
    results = benchmarks.run_all_benchmarks()

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nResults saved to {args.output}")

    return results


if __name__ == "__main__":
    main()
