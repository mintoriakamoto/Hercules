"""Advanced agent combining all capabilities for world-class coding.

Integrates:
- Code understanding (AST, dependency analysis)
- Multi-path planning (Tree-of-Thought)
- Context optimization (sliding window)
- Error recovery (self-healing)
- Performance tracking (metrics)
- Autonomy control (safety)
- Capabilities learning (adaptation)
"""

from pathlib import Path
from typing import Optional, List
from agent.code_understanding import CodeRepository, CodeAnalyzer
from agent.planning.tree_of_thought import TreeOfThought
from agent.context_optimization import ContextWindow
from agent.error_recovery import ErrorRecovery
from agent.performance_analytics import PerformanceTracker
from agent.autonomy_control import AutonomyController, AutonomyLevel
from agent.capabilities_registry import CapabilitiesRegistry


class AdvancedCodingAgent:
    """World-class coding agent with all advanced capabilities."""

    def __init__(self, autonomy_level: AutonomyLevel = AutonomyLevel.SEMI_AUTO):
        """Initialize advanced agent."""
        self.code_repo = CodeRepository()
        self.context_window = ContextWindow(max_tokens=4000)
        self.error_recovery = ErrorRecovery()
        self.performance_tracker = PerformanceTracker()
        self.autonomy = AutonomyController(level=autonomy_level)
        self.capabilities = CapabilitiesRegistry()
        self.task_count = 0

    def understand_codebase(self, filepath: str) -> dict:
        """Deep code understanding."""
        analyzer = CodeAnalyzer(Path(filepath))
        related_files = self.code_repo.find_related_files(filepath)

        return {
            "target": analyzer.get_summary(),
            "related_files": list(related_files),
            "complexity": self.code_repo.get_complexity_report(),
        }

    async def plan_implementation(
        self,
        task: str,
        context: str,
        num_approaches: int = 3,
    ) -> List[str]:
        """Generate multiple implementation approaches."""
        def evaluator(approach: str) -> float:
            # Evaluate approach quality (0-1)
            factors = []
            if "simple" in approach.lower():
                factors.append(0.8)
            if "async" in approach.lower():
                factors.append(0.7)
            if "error" in approach.lower():
                factors.append(0.9)
            return sum(factors) / len(factors) if factors else 0.5

        def generator(current: str) -> List[str]:
            # Generate next possible approaches
            return [
                f"{current} -> Async implementation",
                f"{current} -> Simple synchronous",
                f"{current} -> With caching",
                f"{current} -> Error handling first",
            ]

        planner = TreeOfThought(
            initial_state=task,
            evaluator=evaluator,
            generator=generator,
            beam_width=num_approaches,
        )

        return await planner.explore()

    def add_context(self, content: str, context_type: str, **metadata):
        """Add content to context window."""
        self.context_window.add_item(content, context_type, **metadata)

    def get_execution_context(self) -> str:
        """Get optimized context for execution."""
        return self.context_window.get_context()

    def execute_task(
        self,
        task_description: str,
        task_fn: callable,
        expected_duration_s: float = 30,
    ) -> tuple:
        """Execute task with full tracking and recovery."""
        import time
        capabilities_used = ["code_understanding", "planning", "execution"]

        # Check if can execute
        if not self.autonomy.can_execute(task_description):
            return False, "Execution not approved or limits exceeded"

        start_time = time.time()
        success = False
        error_msg = ""

        try:
            # Execute
            result = task_fn()
            success = True

        except Exception as e:
            # Diagnose and attempt recovery
            diagnosis = self.error_recovery.diagnose(e)
            error_msg = diagnosis.message

            if diagnosis.severity.value == "critical":
                success = False
            else:
                # Attempt recovery
                if self.error_recovery.attempt_recovery(diagnosis):
                    success = True
                    capabilities_used.append("error_recovery")

        # Track performance
        elapsed = time.time() - start_time
        self.performance_tracker.record_operation(
            task_description,
            elapsed * 1000,
            0,  # tokens would be tracked separately
            "claude-sonnet",
            success=success,
        )

        # Record in capabilities
        self.capabilities.record_task(
            task_description,
            capabilities_used,
            success,
            elapsed * 1000,
        )

        # Update autonomy usage
        self.autonomy.record_usage(
            api_calls=1,
            execution_time_s=elapsed,
        )

        self.task_count += 1
        return success, error_msg

    def get_agent_status(self) -> dict:
        """Get comprehensive agent status."""
        return {
            "tasks_completed": self.task_count,
            "autonomy": self.autonomy.get_status(),
            "capabilities": self.capabilities.get_capability_profile(),
            "performance": self.performance_tracker.get_model_comparison(),
        }


__all__ = ["AdvancedCodingAgent"]
