#!/usr/bin/env python3
"""
AOT Integration - Unified Interface for All Acceleration Strategies

Provides a single integration point that:
1. Analyzes tool schemas
2. Selects optimal compilation strategy
3. Manages compilation pipeline
4. Handles fallback gracefully
5. Integrates with registry

Pipeline Decision Tree:
    Tool Schema
        ↓
    Is Numerical? → Yes → Mojo/JAX acceleration
        ↓ No
    Is Simple? → Yes → Cython AOT
        ↓ No
    Is Hot? (from profiler) → Yes → LLVM IR generation
        ↓ No
    Use Runtime Codegen for specialization
"""

import logging
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class AOTCompilationStrategy:
    """Selects and orchestrates AOT compilation."""

    def __init__(self):
        self.compiled_tools: Dict[str, Callable] = {}
        self.compilation_stats: Dict[str, Dict[str, Any]] = {}

    def analyze_tool(
        self,
        tool_name: str,
        handler: Callable,
        schema: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Analyze tool to determine optimal compilation strategy.

        Returns:
            Analysis with recommended strategy, complexity score, speedup potential
        """
        analysis = {
            'tool_name': tool_name,
            'schema_complexity': self._compute_schema_complexity(schema),
            'is_numerical': self._is_numerical_tool(schema),
            'is_simple': self._is_simple_tool(schema),
            'compilation_strategies': [],
            'recommended_strategy': None,
            'speedup_potential': 1.0,
        }

        # Evaluate each strategy
        strategies = [
            ('mojo_jax', self._check_mojo_strategy, 50.0),
            ('cython_aot', self._check_cython_strategy, 25.0),
            ('llvm_ir', self._check_llvm_strategy, 15.0),
            ('codegen', self._check_codegen_strategy, 5.0),
        ]

        for strategy_name, checker, speedup in strategies:
            if checker(schema):
                analysis['compilation_strategies'].append({
                    'name': strategy_name,
                    'applicable': True,
                    'speedup_potential': speedup,
                })

        # Recommend best strategy
        if analysis['compilation_strategies']:
            best = max(
                analysis['compilation_strategies'],
                key=lambda s: s['speedup_potential']
            )
            analysis['recommended_strategy'] = best['name']
            analysis['speedup_potential'] = best['speedup_potential']

        return analysis

    def _compute_schema_complexity(self, schema: Dict[str, Any]) -> float:
        """Compute schema complexity score (0-1)."""
        params = schema.get("parameters", {}).get("properties", {})
        complexity = min(1.0, len(params) / 20.0)  # Normalize to 0-1
        return complexity

    def _is_numerical_tool(self, schema: Dict[str, Any]) -> bool:
        """Check if tool is primarily numerical."""
        params = schema.get("parameters", {}).get("properties", {})
        numerical_count = sum(
            1 for p in params.values()
            if p.get("type") in ("number", "integer", "array")
        )
        return numerical_count > len(params) * 0.5  # More than 50% numerical

    def _is_simple_tool(self, schema: Dict[str, Any]) -> bool:
        """Check if tool has simple signature."""
        params = schema.get("parameters", {}).get("properties", {})
        return len(params) <= 5  # 5 or fewer parameters

    def _check_mojo_strategy(self, schema: Dict[str, Any]) -> bool:
        """Check if Mojo/JAX strategy applies."""
        from tools.mojo_tool_kernel import get_mojo_compiler

        if not self._is_numerical_tool(schema):
            return False

        compiler = get_mojo_compiler()
        # Would check Mojo availability here
        return self._is_numerical_tool(schema)

    def _check_cython_strategy(self, schema: Dict[str, Any]) -> bool:
        """Check if Cython AOT strategy applies."""
        # Applies to most tools
        return True

    def _check_llvm_strategy(self, schema: Dict[str, Any]) -> bool:
        """Check if LLVM IR strategy applies."""
        # Applies to moderate complexity tools
        complexity = self._compute_schema_complexity(schema)
        return complexity > 0.3

    def _check_codegen_strategy(self, schema: Dict[str, Any]) -> bool:
        """Check if runtime codegen strategy applies."""
        # Fallback strategy - always applicable
        return True

    def apply_compilation(
        self,
        tool_name: str,
        handler: Callable,
        schema: Dict[str, Any],
        strategy: Optional[str] = None,
    ) -> Optional[Callable]:
        """Apply AOT compilation with selected strategy.

        Args:
            tool_name: Tool name
            handler: Handler function
            schema: Tool schema
            strategy: Specific strategy to use, or None for auto-detect

        Returns:
            Compiled handler, or None if compilation fails
        """
        if strategy is None:
            analysis = self.analyze_tool(tool_name, handler, schema)
            strategy = analysis['recommended_strategy']
            if not strategy:
                return None

        try:
            if strategy == 'mojo_jax':
                return self._apply_mojo_jax(tool_name, handler, schema)
            elif strategy == 'cython_aot':
                return self._apply_cython_aot(tool_name, handler, schema)
            elif strategy == 'llvm_ir':
                return self._apply_llvm_ir(tool_name, handler, schema)
            elif strategy == 'codegen':
                return self._apply_codegen(tool_name, handler, schema)
        except Exception as e:
            logger.warning(f"Compilation failed for {tool_name}: {e}")

        return None

    def _apply_mojo_jax(
        self,
        tool_name: str,
        handler: Callable,
        schema: Dict[str, Any],
    ) -> Optional[Callable]:
        """Apply Mojo/JAX acceleration."""
        logger.debug(f"Applying Mojo/JAX strategy to {tool_name}")

        try:
            from tools.mojo_tool_kernel import JAXAccelerator

            accelerator = JAXAccelerator()
            compiled = accelerator.generate_jax_kernel(tool_name, handler)

            if compiled:
                self.compiled_tools[tool_name] = compiled
                self.compilation_stats[tool_name] = {
                    'strategy': 'mojo_jax',
                    'speedup_potential': 50.0,
                }
                return compiled
        except Exception as e:
            logger.debug(f"Mojo/JAX failed: {e}")

        return None

    def _apply_cython_aot(
        self,
        tool_name: str,
        handler: Callable,
        schema: Dict[str, Any],
    ) -> Optional[Callable]:
        """Apply Cython AOT compilation."""
        logger.debug(f"Applying Cython AOT strategy to {tool_name}")

        try:
            from tools.aot_compiler import get_aot_compiler, ToolSchema

            tool_schema = ToolSchema(
                name=tool_name,
                handler=handler,
                schema=schema,
                module_path="",
            )

            compiler = get_aot_compiler()
            result = compiler.compile_tool(tool_schema)

            if result.success:
                self.compilation_stats[tool_name] = {
                    'strategy': 'cython_aot',
                    'speedup_potential': result.speedup_estimate,
                    'native_size_bytes': result.native_size_bytes,
                }
                # In production, would load the compiled .so
                return handler  # Placeholder
        except Exception as e:
            logger.debug(f"Cython AOT failed: {e}")

        return None

    def _apply_llvm_ir(
        self,
        tool_name: str,
        handler: Callable,
        schema: Dict[str, Any],
    ) -> Optional[Callable]:
        """Apply LLVM IR generation."""
        logger.debug(f"Applying LLVM IR strategy to {tool_name}")

        try:
            from tools.llvm_codegen import get_ir_generator

            ir_gen = get_ir_generator()
            ir_code = ir_gen.generate_ir_for_tool(tool_name, schema)
            obj_file = ir_gen.compile_ir_to_object(ir_code, tool_name)

            if obj_file:
                self.compilation_stats[tool_name] = {
                    'strategy': 'llvm_ir',
                    'speedup_potential': 15.0,
                    'object_file': str(obj_file),
                }
                # In production, would link the object file
                return handler  # Placeholder
        except Exception as e:
            logger.debug(f"LLVM IR failed: {e}")

        return None

    def _apply_codegen(
        self,
        tool_name: str,
        handler: Callable,
        schema: Dict[str, Any],
    ) -> Optional[Callable]:
        """Apply runtime code generation."""
        logger.debug(f"Applying codegen strategy to {tool_name}")

        try:
            from tools.codegen_dispatch import get_specialized_dispatcher

            dispatcher = get_specialized_dispatcher()
            compiled = dispatcher.compile_dispatcher(tool_name, handler, schema)

            self.compiled_tools[tool_name] = compiled
            self.compilation_stats[tool_name] = {
                'strategy': 'codegen',
                'speedup_potential': 5.0,
            }

            return compiled
        except Exception as e:
            logger.debug(f"Codegen failed: {e}")

        return None

    def get_summary(self) -> Dict[str, Any]:
        """Get compilation summary."""
        return {
            'total_compiled': len(self.compiled_tools),
            'compilation_stats': self.compilation_stats,
            'avg_speedup_potential': (
                sum(
                    s.get('speedup_potential', 1.0)
                    for s in self.compilation_stats.values()
                ) / len(self.compilation_stats)
                if self.compilation_stats else 1.0
            ),
        }


# Global strategy instance
_global_strategy: Optional[AOTCompilationStrategy] = None


def get_aot_strategy() -> AOTCompilationStrategy:
    """Get or create global AOT strategy."""
    global _global_strategy
    if _global_strategy is None:
        _global_strategy = AOTCompilationStrategy()
    return _global_strategy


def integrate_with_registry(registry_module: Any) -> None:
    """Integrate AOT compilation with tool registry.

    This would be called from registry.py to hook AOT compilation
    into the tool dispatch pipeline.

    Args:
        registry_module: The tools.registry module
    """
    original_dispatch = registry_module.dispatch
    strategy = get_aot_strategy()

    def aot_aware_dispatch(tool_name: str, arguments: dict) -> Any:
        """Dispatch with AOT compilation awareness."""
        # Check if we have a compiled version
        if tool_name in strategy.compiled_tools:
            try:
                compiled = strategy.compiled_tools[tool_name]
                return compiled(arguments)
            except Exception as e:
                logger.debug(f"Compiled dispatch failed, falling back: {e}")

        # Fall back to original
        return original_dispatch(tool_name, arguments)

    # Replace original dispatch
    registry_module.dispatch = aot_aware_dispatch
    logger.info("AOT compilation integrated with registry")
