"""
JIT Integration Module: Hook JIT compilation into the agent loop.

Provides utilities to integrate JIT profiling and compilation into
the main agent conversation loop without modifying core agent code.

Usage in agent/conversation_loop.py:
  1. At turn start: Collect profiling hints
  2. After tool dispatch: Record execution times
  3. At turn end: Check for compilation candidates and trigger background compilation
  4. On hot tool detection: Use compiled paths automatically via registry.dispatch()
"""

import logging
import threading
import time
from typing import Optional, Dict, List, Any
from pathlib import Path

from tools.jit_profiler import get_global_profiler, JITProfiler
from tools.jit_compiler import get_global_compiler, JITCompiler

logger = logging.getLogger(__name__)


class JITIntegrationHooks:
    """Integration points for JIT compilation into the agent loop."""

    def __init__(self):
        self.profiler = get_global_profiler()
        self.compiler = get_global_compiler()
        self.compilation_thread: Optional[threading.Thread] = None
        self.enable_background_compilation = True
        self.compilation_interval_ms = 5000  # Check every 5 seconds

    def record_tool_execution(
        self,
        tool_name: str,
        duration_ms: float,
        success: bool = True,
        error_type: Optional[str] = None,
    ) -> None:
        """
        Record a tool execution for profiling.

        Called from handle_function_call or registry.dispatch.

        Args:
            tool_name: Name of the tool
            duration_ms: Execution time in milliseconds
            success: Whether the call succeeded
            error_type: Type of error if failed
        """
        self.profiler.record_call(tool_name, duration_ms, success, error_type)

    def suggest_compilation(self) -> List[str]:
        """
        Check if hot tools should be compiled.

        Returns:
            List of tool names recommended for compilation
        """
        return self.profiler.suggest_compilation_targets(min_call_count=10)

    def compile_hot_tools_background(
        self, tools_registry: "ToolRegistry"
    ) -> threading.Thread:
        """
        Start background compilation of hot tools.

        This runs in a separate thread to avoid blocking the agent loop.

        Args:
            tools_registry: The tool registry instance

        Returns:
            Thread object (for testing/joining)
        """
        if self.compilation_thread and self.compilation_thread.is_alive():
            return self.compilation_thread

        def _compile():
            """Background compilation worker."""
            while self.enable_background_compilation:
                try:
                    hot_tools = self.suggest_compilation()
                    for tool_name in hot_tools:
                        if self.compiler.should_use_compiled_path(tool_name):
                            continue  # Already compiled

                        try:
                            entry = tools_registry.get_entry(tool_name)
                            if entry:
                                self.compiler.compile_tool(
                                    tool_name=tool_name,
                                    handler=entry.handler,
                                    schema=entry.schema,
                                )
                                logger.debug(
                                    f"Background compiled hot tool: {tool_name}"
                                )
                        except Exception as e:
                            logger.warning(
                                f"Failed to background compile {tool_name}: {e}"
                            )

                    time.sleep(self.compilation_interval_ms / 1000.0)
                except Exception as e:
                    logger.warning(f"Background compilation thread error: {e}")
                    time.sleep(1)

        thread = threading.Thread(target=_compile, daemon=True, name="jit-compiler")
        thread.start()
        self.compilation_thread = thread
        return thread

    def get_profiling_summary(self) -> Dict[str, Any]:
        """Get current profiling summary."""
        return self.profiler.get_profile_summary()

    def get_compilation_stats(self) -> Dict[str, Any]:
        """Get current compilation statistics."""
        return self.compiler.get_compilation_stats()

    def save_profiling_report(self, path: Path) -> None:
        """Save profiling data to disk."""
        self.profiler.save_profile(path)
        logger.info(f"Profiling report saved to {path}")

    def save_compilation_report(self, path: Path) -> None:
        """Save compilation data to disk."""
        self.compiler.save_compilation_report(path)
        logger.info(f"Compilation report saved to {path}")

    def should_trigger_compilation_pass(
        self, min_calls: int = 100
    ) -> bool:
        """
        Check if it's time for a compilation pass.

        Returns True if:
        - We've profiled enough calls (min_calls)
        - There are uncompiled hot tools
        """
        if self.profiler.total_calls < min_calls:
            return False

        hot_tools = self.suggest_compilation()
        return any(
            not self.compiler.should_use_compiled_path(name)
            for name in hot_tools
        )


# Global integration instance
_integration: Optional[JITIntegrationHooks] = None


def get_jit_hooks() -> JITIntegrationHooks:
    """Get or create the global JIT integration hooks."""
    global _integration
    if _integration is None:
        _integration = JITIntegrationHooks()
    return _integration


# ============================================================================
# AGENT LOOP INTEGRATION EXAMPLES
# ============================================================================

def integrate_with_conversation_loop(agent):
    """
    Example integration with agent/conversation_loop.py.

    This would be called at the start of run_conversation().
    """
    hooks = get_jit_hooks()

    # Store reference to registry for background compilation
    try:
        from tools.registry import registry
        hooks.compile_hot_tools_background(registry)
    except Exception as e:
        logger.warning(f"Failed to initialize background JIT compilation: {e}")


def record_tool_execution_hook(
    tool_name: str,
    duration_ms: float,
    success: bool = True,
):
    """
    Hook to be called after every tool execution.

    Example usage in handle_function_call or registry.dispatch:
        try:
            result = tool.handler(args)
            record_tool_execution_hook(tool_name, elapsed_ms, success=True)
        except Exception as e:
            record_tool_execution_hook(tool_name, elapsed_ms, success=False)
            raise
    """
    hooks = get_jit_hooks()
    hooks.record_tool_execution(tool_name, duration_ms, success)

    # Periodically check if compilation is needed
    if hooks.should_trigger_compilation_pass():
        try:
            from tools.registry import registry
            hooks.compile_hot_tools_background(registry)
        except Exception as e:
            logger.warning(f"Failed to trigger background compilation: {e}")


def emit_profiling_report(path: Path) -> None:
    """Emit profiling report to disk (called at agent shutdown)."""
    hooks = get_jit_hooks()
    hooks.save_profiling_report(path)
    hooks.save_compilation_report(path.parent / "compilation.json")


# ============================================================================
# MONITORING AND DEBUGGING
# ============================================================================

def print_jit_status() -> str:
    """Get human-readable JIT status."""
    hooks = get_jit_hooks()
    summary = hooks.get_profiling_summary()
    stats = hooks.get_compilation_stats()

    lines = [
        "=" * 60,
        "JIT ACCELERATION STATUS",
        "=" * 60,
        f"Total tool calls: {summary.get('total_tool_calls', 0)}",
        f"Unique tools: {summary.get('unique_tools', 0)}",
        f"Hot tools identified: {summary.get('hot_tools_count', 0)}",
        f"Compiled tools: {stats.get('total_compiled_tools', 0)}",
        f"Compilation time (total): {stats.get('total_compile_time_ms', 0):.1f}ms",
        f"Execution speedup: {stats.get('total_execution_time_ms', 0) / max(1, stats.get('total_compiled_calls', 1)) * 1000:.3f}µs avg",
        "",
        "HOT TOOLS:",
    ]

    for hot_tool in summary.get("hot_tools", [])[:10]:
        lines.append(
            f"  - {hot_tool['name']}: "
            f"{hot_tool['call_count']} calls, "
            f"{hot_tool['avg_time_ms']:.2f}ms avg"
        )

    return "\n".join(lines)
