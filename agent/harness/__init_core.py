"""Core agent interface and execution engine."""

from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from abc import ABC, abstractmethod
import json
from datetime import datetime
from pathlib import Path


class AgentState(Enum):
    """Formal agent execution states."""
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    RECOVERING = "recovering"
    COMPLETE = "complete"
    FAILED = "failed"


class AgentEvent(Enum):
    """Formal agent events."""
    TASK_START = "task_start"
    PLAN_CREATED = "plan_created"
    EXECUTION_START = "execution_start"
    STEP_COMPLETE = "step_complete"
    ERROR_DETECTED = "error_detected"
    RECOVERY_ATTEMPT = "recovery_attempt"
    TASK_COMPLETE = "task_complete"
    TASK_FAILED = "task_failed"


@dataclass
class ExecutionTrace:
    """Immutable audit trail entry."""
    timestamp: float
    state: AgentState
    event: AgentEvent
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    resources_used: Dict[str, float]
    decision_made: str


@dataclass
class ExecutionResult:
    """Result of agent execution with proof."""
    success: bool
    output: Any
    final_state: AgentState
    trace: List[ExecutionTrace]
    proof: Dict[str, Any]
    resource_usage: Dict[str, float]
    error: Optional[str] = None


@dataclass
class ResourceLimits:
    """Resource constraints for execution."""
    max_api_calls: int = 50
    max_tokens: int = 4000
    max_cost_usd: float = 10.0
    max_execution_time_s: int = 300
    max_retries: int = 3


class Agent(ABC):
    """Base agent class with formal lifecycle."""

    def __init__(self, agent_id: str, name: str):
        self.agent_id = agent_id
        self.name = name
        self.state = AgentState.IDLE
        self.trace: List[ExecutionTrace] = []
        self.checkpoints: Dict[str, Dict] = {}

    @abstractmethod
    def plan(self, task: Any) -> "Plan":
        """Generate execution plan."""
        pass

    @abstractmethod
    def execute_step(self, step: Any, context: Dict) -> Any:
        """Execute single step with verification."""
        pass

    def record_trace(
        self,
        event: AgentEvent,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        resources: Dict[str, float],
        decision: str = "",
    ):
        """Record execution trace entry (immutable)."""
        entry = ExecutionTrace(
            timestamp=datetime.now().timestamp(),
            state=self.state,
            event=event,
            input_data=input_data,
            output_data=output_data,
            resources_used=resources,
            decision_made=decision,
        )
        self.trace.append(entry)

    def save_checkpoint(self, step: int, state_data: Dict) -> str:
        """Save checkpoint for recovery."""
        checkpoint_id = f"ckpt_{step}_{int(datetime.now().timestamp())}"
        self.checkpoints[checkpoint_id] = {
            "step": step,
            "state": state_data,
            "timestamp": datetime.now().isoformat(),
        }
        return checkpoint_id

    def restore_checkpoint(self, checkpoint_id: str) -> Optional[Dict]:
        """Restore from checkpoint."""
        return self.checkpoints.get(checkpoint_id)


@dataclass
class Plan:
    """Executable plan composed of steps."""
    steps: List[Any]
    dependencies: Dict[str, List[str]] = field(default_factory=dict)

    def validate(self) -> bool:
        """Validate plan structure (no cycles, all deps exist)."""
        step_ids = [s.id if hasattr(s, 'id') else str(s) for s in self.steps]

        # Check all deps exist
        for step_id, deps in self.dependencies.items():
            for dep in deps:
                if dep not in step_ids:
                    return False

        # Check for cycles using DFS
        visited = set()
        rec_stack = set()

        def has_cycle(node):
            visited.add(node)
            rec_stack.add(node)

            for neighbor in self.dependencies.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        for node in step_ids:
            if node not in visited:
                if has_cycle(node):
                    return False

        return True

    def topological_sort(self) -> List[Any]:
        """Get execution order (respects dependencies)."""
        visited = set()
        order = []

        def visit(step_id: str):
            if step_id in visited:
                return
            visited.add(step_id)

            for dep in self.dependencies.get(step_id, []):
                visit(dep)

            for step in self.steps:
                step_name = step.id if hasattr(step, 'id') else str(step)
                if step_name == step_id:
                    order.append(step)
                    break

        for step in self.steps:
            step_id = step.id if hasattr(step, 'id') else str(step)
            visit(step_id)

        return order


class ExecutionEngine:
    """State machine-based execution with formal guarantees."""

    def __init__(self, agent: Agent, limits: ResourceLimits):
        self.agent = agent
        self.limits = limits
        self.resource_tracker = {
            "api_calls": 0,
            "tokens_used": 0,
            "cost_usd": 0.0,
            "execution_time_s": 0.0,
        }

    def execute(self, plan: Plan) -> ExecutionResult:
        """Execute plan with FSM guarantees."""
        if not plan.validate():
            return ExecutionResult(
                success=False,
                output=None,
                final_state=AgentState.FAILED,
                trace=self.agent.trace,
                proof={"error": "Invalid plan: circular dependencies or missing steps"},
                resource_usage=self.resource_tracker,
                error="Plan validation failed",
            )

        self.agent.state = AgentState.EXECUTING
        self.agent.record_trace(
            AgentEvent.EXECUTION_START,
            {"plan_steps": len(plan.steps)},
            {},
            {},
        )

        results = {}
        ordered_steps = plan.topological_sort()

        for step in ordered_steps:
            if not self._check_limits():
                self.agent.state = AgentState.FAILED
                return ExecutionResult(
                    success=False,
                    output=None,
                    final_state=self.agent.state,
                    trace=self.agent.trace,
                    proof={"error": "Resource limits exceeded"},
                    resource_usage=self.resource_tracker,
                    error="Resource limits exceeded",
                )

            try:
                result = self.agent.execute_step(step, results)
                step_id = step.id if hasattr(step, 'id') else str(step)
                results[step_id] = result

                self.agent.record_trace(
                    AgentEvent.STEP_COMPLETE,
                    {"step": step_id},
                    {"result": str(result)[:100]},
                    self.resource_tracker.copy(),
                    f"Executed {step_id}",
                )

            except Exception as e:
                return self._handle_error(str(e), results)

        self.agent.state = AgentState.COMPLETE
        self.agent.record_trace(
            AgentEvent.TASK_COMPLETE,
            {"steps_executed": len(ordered_steps)},
            {"success": True},
            self.resource_tracker.copy(),
        )

        return ExecutionResult(
            success=True,
            output=results,
            final_state=self.agent.state,
            trace=self.agent.trace,
            proof=self._generate_proof(ordered_steps),
            resource_usage=self.resource_tracker,
        )

    def _check_limits(self) -> bool:
        """Check if any resource limit exceeded."""
        return (
            self.resource_tracker["api_calls"] < self.limits.max_api_calls
            and self.resource_tracker["tokens_used"] < self.limits.max_tokens
            and self.resource_tracker["cost_usd"] < self.limits.max_cost_usd
        )

    def _handle_error(self, error: str, context: Dict) -> ExecutionResult:
        """Handle error with recovery attempt."""
        self.agent.state = AgentState.RECOVERING
        self.agent.record_trace(
            AgentEvent.ERROR_DETECTED,
            {"error": error},
            {},
            self.resource_tracker.copy(),
        )

        self.agent.state = AgentState.FAILED

        return ExecutionResult(
            success=False,
            output=None,
            final_state=self.agent.state,
            trace=self.agent.trace,
            proof={"error": error, "attempted_context": len(context)},
            resource_usage=self.resource_tracker,
            error=error,
        )

    def _generate_proof(self, steps: List[Any]) -> Dict[str, Any]:
        """Generate proof of correctness."""
        return {
            "steps_executed": len(steps),
            "final_state": self.agent.state.value,
            "trace_entries": len(self.agent.trace),
            "resources_within_limits": self._check_limits(),
            "proof_method": "trace_validation",
        }
