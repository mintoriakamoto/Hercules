#!/usr/bin/env python3
"""SIMD Vectorization Benchmark Suite

Comprehensive benchmarks for SIMD-accelerated JSON parsing, schema caching,
and argument parsing components. Measures:

1. JSON parsing speedup (5-10x target)
2. Schema cache batch operations (50x target)
3. Argument validation throughput (10-20x target)
4. CPU utilization and cache efficiency
5. End-to-end tool call pipeline

Usage:
    python tools/bench_simd.py [--profile] [--verbose] [--save-results]
"""

import json
import time
import sys
import gc
import statistics
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from collections import defaultdict

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.simd_json_parser import SIMDJsonParser, get_simd_parser
from tools.vectorized_schema_cache import VectorizedSchemaCache, get_schema_cache
from tools.simd_arg_parser import SIMDArgumentParser, get_argument_parser


class SIMDBenchmarkTimer:
    """Precise timing context manager."""

    def __init__(self, name: str = ""):
        self.name = name
        self.start_time = None
        self.elapsed_ms = 0.0
        self.iterations = 0

    def __enter__(self):
        gc.collect()
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.elapsed_ms = (time.perf_counter() - self.start_time) * 1000.0

    def per_iteration_ms(self) -> float:
        """Average time per iteration."""
        return self.elapsed_ms / self.iterations if self.iterations > 0 else 0.0


class SIMDBenchmarks:
    """Complete SIMD benchmark suite."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results = defaultdict(dict)

    def _log(self, msg: str):
        """Print benchmark message."""
        if self.verbose:
            print(f"[BENCH] {msg}", flush=True)

    # =========================================================================
    # JSON PARSING BENCHMARKS
    # =========================================================================

    def _generate_tool_call_payload(self, num_calls: int = 10, args_per_call: int = 5) -> str:
        """Generate realistic tool call JSON payload."""
        calls = []
        for i in range(num_calls):
            args = {}
            for j in range(args_per_call):
                args[f"arg_{j}"] = f"value_{i}_{j}"

            calls.append({
                "id": f"call_{i}",
                "function": {
                    "name": f"tool_{i % 5}",
                    "arguments": json.dumps(args)
                }
            })

        return json.dumps({"tool_calls": calls})

    def benchmark_json_parsing(self) -> Dict[str, Any]:
        """Benchmark JSON parsing with SIMD vs scalar."""
        self._log("Starting JSON parsing benchmark...")

        # Generate test payloads of varying sizes
        test_sizes = [10, 50, 100, 500, 1000]
        results = {
            "simd": {},
            "scalar": {},
            "speedup": {}
        }

        parser_simd = SIMDJsonParser(use_simd=True)
        parser_scalar = SIMDJsonParser(use_simd=False)

        for size in test_sizes:
            payload = self._generate_tool_call_payload(size)

            # Benchmark SIMD
            iterations = max(10, 100 // max(1, size // 10))
            with SIMDBenchmarkTimer(f"SIMD JSON {size} calls") as timer:
                for _ in range(iterations):
                    result = parser_simd.parse_tool_calls_array(payload)
                    if result is None:
                        raise ValueError(f"SIMD parsing failed for {size} calls")
                timer.iterations = iterations
            simd_time = timer.per_iteration_ms()
            results["simd"][size] = simd_time

            # Benchmark scalar
            with SIMDBenchmarkTimer(f"Scalar JSON {size} calls") as timer:
                for _ in range(iterations):
                    result = parser_scalar.parse_tool_calls_array(payload)
                    if result is None:
                        raise ValueError(f"Scalar parsing failed for {size} calls")
                timer.iterations = iterations
            scalar_time = timer.per_iteration_ms()
            results["scalar"][size] = scalar_time

            # Calculate speedup
            speedup = scalar_time / simd_time if simd_time > 0 else 0
            results["speedup"][size] = speedup

            self._log(f"  {size} calls: {scalar_time:.3f}ms → {simd_time:.3f}ms ({speedup:.1f}x)")

        return results

    # =========================================================================
    # SCHEMA CACHE BENCHMARKS
    # =========================================================================

    def _generate_tool_schemas(self, num_tools: int = 100) -> List[Tuple[str, Dict]]:
        """Generate realistic tool schemas."""
        schemas = []
        for i in range(num_tools):
            schema = {
                "name": f"tool_{i}",
                "description": f"Tool {i} description",
                "parameters": {
                    "type": "object",
                    "properties": {
                        f"param_{j}": {
                            "type": "string",
                            "description": f"Parameter {j}"
                        }
                        for j in range(3)
                    },
                    "required": ["param_0"]
                }
            }
            schemas.append((f"tool_{i}", schema))

        return schemas

    def benchmark_schema_cache(self) -> Dict[str, Any]:
        """Benchmark schema cache operations."""
        self._log("Starting schema cache benchmark...")

        schemas = self._generate_tool_schemas(500)

        # Populate cache
        cache = VectorizedSchemaCache(use_simd=True)
        for name, schema in schemas:
            cache.put(name, schema)

        results = {}

        # Benchmark single lookups
        tool_names = [s[0] for s in schemas]
        with SIMDBenchmarkTimer("Single lookup") as timer:
            for _ in range(1000):
                cache.get(tool_names[0])
            timer.iterations = 1000
        results["single_lookup_ms"] = timer.per_iteration_ms()

        # Benchmark batch lookups
        batch_sizes = [10, 50, 100, 500]
        results["batch_lookup"] = {}

        for batch_size in batch_sizes:
            batch_names = tool_names[:batch_size]
            iterations = max(5, 100 // batch_size)

            with SIMDBenchmarkTimer(f"Batch {batch_size}") as timer:
                for _ in range(iterations):
                    cache.get_batch(batch_names)
                timer.iterations = iterations

            time_per_item = timer.per_iteration_ms() / batch_size
            results["batch_lookup"][batch_size] = {
                "total_ms": timer.per_iteration_ms(),
                "per_item_us": time_per_item * 1000
            }

            self._log(f"  Batch {batch_size}: {timer.per_iteration_ms():.2f}ms "
                     f"({time_per_item * 1000:.1f}µs per item)")

        # Get statistics
        stats = cache.get_statistics()
        results["stats"] = stats

        return results

    # =========================================================================
    # ARGUMENT PARSING BENCHMARKS
    # =========================================================================

    def _generate_argument_set(self, num_args: int = 10) -> Tuple[Dict, Dict, Dict]:
        """Generate schema and arguments for testing."""
        schema = {
            "type": "object",
            "properties": {
                f"arg_{i}": {
                    "type": "string" if i % 3 == 0 else "number" if i % 3 == 1 else "boolean",
                    "description": f"Argument {i}"
                }
                for i in range(num_args)
            },
            "required": [f"arg_{i}" for i in range(num_args // 2)]
        }

        arguments = {
            f"arg_{i}": f"value_{i}" if i % 3 == 0 else str(i * 1.5) if i % 3 == 1 else (i % 2 == 0)
            for i in range(num_args)
        }

        return schema, arguments, schema

    def benchmark_argument_parsing(self) -> Dict[str, Any]:
        """Benchmark argument validation and coercion."""
        self._log("Starting argument parsing benchmark...")

        parser_simd = SIMDArgumentParser(use_simd=True)
        parser_scalar = SIMDArgumentParser(use_simd=False)

        arg_counts = [10, 50, 100, 500]
        results = {}

        for arg_count in arg_counts:
            schema, arguments, _ = self._generate_argument_set(arg_count)
            iterations = max(5, 100 // (arg_count // 10 + 1))

            # Benchmark SIMD
            with SIMDBenchmarkTimer(f"SIMD parse {arg_count}") as timer:
                for _ in range(iterations):
                    validated, errors = parser_simd.validate_and_coerce(schema, arguments)
                timer.iterations = iterations
            simd_time = timer.per_iteration_ms()

            # Benchmark scalar
            with SIMDBenchmarkTimer(f"Scalar parse {arg_count}") as timer:
                for _ in range(iterations):
                    validated, errors = parser_scalar.validate_and_coerce(schema, arguments)
                timer.iterations = iterations
            scalar_time = timer.per_iteration_ms()

            speedup = scalar_time / simd_time if simd_time > 0 else 0
            results[arg_count] = {
                "simd_ms": simd_time,
                "scalar_ms": scalar_time,
                "speedup": speedup
            }

            self._log(f"  {arg_count} args: {scalar_time:.3f}ms → {simd_time:.3f}ms ({speedup:.1f}x)")

        return results

    # =========================================================================
    # INTEGRATION BENCHMARKS
    # =========================================================================

    def benchmark_full_pipeline(self) -> Dict[str, Any]:
        """Benchmark complete tool call pipeline with SIMD."""
        self._log("Starting full pipeline benchmark...")

        # Generate realistic workload
        payload = self._generate_tool_call_payload(100, 5)
        schema_cache = get_schema_cache(use_simd=True)
        parser = get_simd_parser(use_simd=True)
        arg_parser = get_argument_parser(use_simd=True)

        # Populate schema cache
        schemas = self._generate_tool_schemas(5)
        for name, schema in schemas:
            schema_cache.put(name, schema)

        iterations = 50
        results = {"iterations": iterations}

        # Benchmark full pipeline
        with SIMDBenchmarkTimer("Full pipeline") as timer:
            for _ in range(iterations):
                # Parse tool calls
                calls = parser.parse_tool_calls_array(payload)
                if not calls:
                    raise ValueError("Failed to parse tool calls")

                # Lookup schemas
                tool_names = [c["function"]["name"] for c in calls]
                schemas_lookup = schema_cache.get_batch(tool_names)

                # Validate arguments
                for call in calls:
                    func = call["function"]
                    tool_name = func["name"]
                    if tool_name in schemas_lookup:
                        schema = schemas_lookup[tool_name]
                        args_str = func.get("arguments", "{}")
                        args = json.loads(args_str)
                        arg_parser.validate_and_coerce(schema, args)

            timer.iterations = iterations

        results["total_ms"] = timer.elapsed_ms
        results["per_iteration_ms"] = timer.per_iteration_ms()
        results["calls_per_second"] = (100 * iterations) / (timer.elapsed_ms / 1000)

        self._log(f"  Full pipeline: {timer.per_iteration_ms():.2f}ms per iteration")
        self._log(f"  Throughput: {results['calls_per_second']:.0f} tool calls/sec")

        return results

    # =========================================================================
    # VALIDATION TESTS
    # =========================================================================

    def validate_correctness(self) -> List[Tuple[str, bool]]:
        """Validate that SIMD produces identical results to scalar."""
        self._log("Running correctness validation...")

        tests = []

        # Test 1: JSON parsing correctness
        parser_simd = SIMDJsonParser(use_simd=True)
        parser_scalar = SIMDJsonParser(use_simd=False)

        payload = self._generate_tool_call_payload(50, 5)
        simd_result = parser_simd.parse_tool_calls_array(payload)
        scalar_result = parser_scalar.parse_tool_calls_array(payload)

        test_pass = simd_result == scalar_result
        tests.append(("JSON parsing correctness", test_pass))
        self._log(f"  JSON parsing: {'PASS' if test_pass else 'FAIL'}")

        # Test 2: Schema cache correctness
        cache = VectorizedSchemaCache(use_simd=True)
        schemas = self._generate_tool_schemas(100)
        for name, schema in schemas:
            cache.put(name, schema)

        for i in range(10):
            single = cache.get(f"tool_{i}")
            batch = cache.get_batch([f"tool_{i}"])
            test_pass = single == batch.get(f"tool_{i}")
            if not test_pass:
                tests.append((f"Schema cache consistency {i}", False))
                break
        else:
            tests.append(("Schema cache consistency", True))
            self._log(f"  Schema cache: PASS")

        # Test 3: Argument validation correctness
        parser_simd = SIMDArgumentParser(use_simd=True)
        parser_scalar = SIMDArgumentParser(use_simd=False)

        schema, arguments, _ = self._generate_argument_set(20)
        simd_val, simd_err = parser_simd.validate_and_coerce(schema, arguments)
        scalar_val, scalar_err = parser_scalar.validate_and_coerce(schema, arguments)

        test_pass = simd_val == scalar_val and len(simd_err) == len(scalar_err)
        tests.append(("Argument validation correctness", test_pass))
        self._log(f"  Argument validation: {'PASS' if test_pass else 'FAIL'}")

        return tests

    def run_all(self) -> Dict[str, Any]:
        """Run complete benchmark suite."""
        print("\n" + "=" * 80)
        print("SIMD VECTORIZATION BENCHMARK SUITE")
        print("=" * 80 + "\n")

        all_results = {}

        print("JSON PARSING BENCHMARKS")
        print("-" * 80)
        all_results["json_parsing"] = self.benchmark_json_parsing()
        print()

        print("SCHEMA CACHE BENCHMARKS")
        print("-" * 80)
        all_results["schema_cache"] = self.benchmark_schema_cache()
        print()

        print("ARGUMENT PARSING BENCHMARKS")
        print("-" * 80)
        all_results["argument_parsing"] = self.benchmark_argument_parsing()
        print()

        print("FULL PIPELINE BENCHMARKS")
        print("-" * 80)
        all_results["full_pipeline"] = self.benchmark_full_pipeline()
        print()

        print("CORRECTNESS VALIDATION")
        print("-" * 80)
        validations = self.validate_correctness()
        all_results["validations"] = validations
        for test_name, passed in validations:
            print(f"  {'✓' if passed else '✗'} {test_name}")
        print()

        # Summary
        print("=" * 80)
        print("BENCHMARK SUMMARY")
        print("=" * 80)

        avg_json_speedup = statistics.mean(all_results["json_parsing"]["speedup"].values())
        print(f"JSON parsing average speedup: {avg_json_speedup:.1f}x")

        arg_speedups = [r["speedup"] for r in all_results["argument_parsing"].values()]
        avg_arg_speedup = statistics.mean(arg_speedups)
        print(f"Argument parsing average speedup: {avg_arg_speedup:.1f}x")

        print(f"Full pipeline throughput: {all_results['full_pipeline']['calls_per_second']:.0f} calls/sec")

        validation_passed = all(passed for _, passed in validations)
        print(f"Validation: {'PASS' if validation_passed else 'FAIL'}")

        return all_results


def main():
    """Run benchmark suite."""
    import argparse

    parser = argparse.ArgumentParser(description="SIMD Vectorization Benchmarks")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--save-results", action="store_true", help="Save results to JSON")
    args = parser.parse_args()

    bench = SIMDBenchmarks(verbose=args.verbose)
    results = bench.run_all()

    if args.save_results:
        output_path = Path("bench_simd_results.json")
        with open(output_path, 'w', encoding="utf-8") as f:
            # Convert some non-serializable values
            json_results = {}
            for key, value in results.items():
                if isinstance(value, dict):
                    json_results[key] = {
                        str(k): v for k, v in value.items()
                        if isinstance(v, (int, float, str, bool, list, dict, type(None)))
                    }
                else:
                    json_results[key] = value
            json.dump(json_results, f, indent=2)
        print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    main()
