"""Subagent orchestration with CORAL and extended reasoning support.

Extends the subagent creation and management to:
- Use reasoning for task decomposition
- Track improvements across subagents
- Enable improvement sharing from parent to children
- Provide observability into subagent reasoning
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from agent.agent_orchestration import get_agent_orchestrator, AgentExecutionContext
from agent.extended_reasoning import get_reasoning_engine

logger = logging.getLogger(__name__)


class SubagentPlan:
    """Plan for decomposing work across subagents."""

    def __init__(
        self,
        parent_agent_id: str,
        num_subagents: int,
        tasks: List[Dict[str, Any]],
    ):
        self.parent_agent_id = parent_agent_id
        self.num_subagents = num_subagents
        self.tasks = tasks
        self.subagent_assignments: Dict[str, List[str]] = {}

    def get_subagent_tasks(self, subagent_id: str) -> List[str]:
        """Get tasks assigned to a specific subagent."""
        return self.subagent_assignments.get(subagent_id, [])

    def assign_task(self, subagent_id: str, task: str) -> None:
        """Assign a task to a subagent."""
        if subagent_id not in self.subagent_assignments:
            self.subagent_assignments[subagent_id] = []
        self.subagent_assignments[subagent_id].append(task)


def plan_subagent_decomposition(
    parent_task: str,
    num_subagents: int,
    available_tools: List[str],
    parent_complexity: Any,  # ReasoningComplexity
) -> SubagentPlan:
    """Plan how to decompose a task across subagents.

    Uses extended reasoning to:
    - Analyze task complexity
    - Identify subtasks
    - Assign tools to subagents
    - Optimize for parallel execution

    Args:
        parent_task: Task being delegated
        num_subagents: Number of subagents to use
        available_tools: Tools available to subagents
        parent_complexity: Complexity level of parent task

    Returns:
        SubagentPlan with task assignments and strategies
    """
    orchestrator = get_agent_orchestrator()
    reasoning_engine = get_reasoning_engine()

    # Analyze subtask opportunities
    plan = SubagentPlan(
        parent_agent_id="parent",
        num_subagents=num_subagents,
        tasks=[],  # Will be populated by reasoning
    )

    # For complex tasks, use reasoning to decompose
    from agent.extended_reasoning import DecisionContext, ReasoningComplexity

    if parent_complexity in [ReasoningComplexity.COMPLEX, ReasoningComplexity.CRITICAL]:
        # Build reasoning context for decomposition
        context = DecisionContext(
            task_description=f"Decompose for {num_subagents} parallel subagents: {parent_task}",
            user_intent="Optimize parallel execution",
            available_tools=available_tools,
            time_budget_seconds=60.0,
            complexity=parent_complexity,
        )

        reasoning = reasoning_engine.build_reasoning_chain(context)

        # Use reasoning to inform subagent assignment
        logger.debug(f"Reasoning for subagent decomposition: {reasoning.reasoning_steps[:2]}")

    # Simple round-robin assignment (can be made smarter with reasoning)
    for i in range(num_subagents):
        subagent_id = f"subagent_{i}"
        plan.subagent_assignments[subagent_id] = []

    return plan


def get_subagent_system_prompt(
    parent_task: str,
    subagent_id: str,
    parent_improvements: Optional[Dict[str, Any]] = None,
) -> str:
    """Build system prompt for a subagent.

    Incorporates:
    - Clear task focus
    - Relevant improvements from parent
    - Recommended tools
    - Constraints and guidelines

    Args:
        parent_task: Task delegated by parent
        subagent_id: ID of this subagent
        parent_improvements: Improvements from parent agent to propagate

    Returns:
        System prompt text for subagent
    """
    prompt_parts = [
        f"You are a specialized subagent ({subagent_id}) executing a delegated task.",
        f"Primary focus: {parent_task}",
        "",
        "Guidelines:",
        "- Complete your assigned task efficiently",
        "- Use reasoning tools to plan complex decisions",
        "- Track performance of each tool you use",
        "- Report both successes and failures",
    ]

    # Add improvement context if available
    if parent_improvements and parent_improvements.get("suggestions"):
        prompt_parts.append("")
        prompt_parts.append("Learn from parent agent improvements:")
        for suggestion in parent_improvements["suggestions"][:3]:
            prompt_parts.append(f"  - {suggestion.get('recommendation', 'N/A')}")

    prompt_parts.extend([
        "",
        "End the task with a summary of:",
        "  1. What was accomplished",
        "  2. Any issues encountered",
        "  3. Tools that worked well",
        "  4. Suggestions for improvement",
    ])

    return "\n".join(prompt_parts)


class SubagentMonitor:
    """Monitor and manage subagent execution."""

    def __init__(self):
        self.active_subagents: Dict[str, Dict[str, Any]] = {}
        self.orchestrator = get_agent_orchestrator()

    def register_subagent(
        self,
        subagent_id: str,
        parent_agent_id: str,
        task_description: str,
    ) -> None:
        """Register a newly spawned subagent.

        Args:
            subagent_id: ID of the subagent
            parent_agent_id: ID of parent agent
            task_description: Task assigned to subagent
        """
        context = self.orchestrator.initialize_agent_context(
            agent_id=subagent_id,
            task_description=task_description,
            parent_agent_id=parent_agent_id,
            depth=1,  # Subagent is depth 1
        )

        self.active_subagents[subagent_id] = {
            "parent_id": parent_agent_id,
            "context": context,
            "start_time": None,
            "executions": [],
        }

    def record_subagent_tool_use(
        self,
        subagent_id: str,
        tool_name: str,
        success: bool,
        latency_ms: float,
    ) -> None:
        """Record tool execution by subagent.

        Args:
            subagent_id: ID of subagent
            tool_name: Tool that was executed
            success: Whether execution succeeded
            latency_ms: Execution time in milliseconds
        """
        if subagent_id in self.active_subagents:
            self.active_subagents[subagent_id]["executions"].append({
                "tool": tool_name,
                "success": success,
                "latency_ms": latency_ms,
            })

        self.orchestrator.record_tool_execution(
            agent_id=subagent_id,
            tool_name=tool_name,
            success=success,
            latency_ms=latency_ms,
        )

    def get_subagent_recommendations(
        self,
        subagent_id: str,
        task: str,
        available_tools: List[str],
    ) -> List[tuple[str, float]]:
        """Get tool recommendations for a subagent.

        Args:
            subagent_id: ID of subagent
            task: Current task
            available_tools: Tools available

        Returns:
            List of (tool_name, relevance_score) tuples
        """
        return self.orchestrator.get_tool_recommendations(
            agent_id=subagent_id,
            task_description=task,
            available_tools=available_tools,
        )

    def finalize_subagent(
        self,
        subagent_id: str,
        success: bool,
        total_time_ms: float,
        tool_count: int,
        summary: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record completion of subagent execution.

        Args:
            subagent_id: ID of subagent
            success: Whether task succeeded
            total_time_ms: Total execution time
            tool_count: Number of tools used
            summary: Optional summary of work

        Returns:
            Final subagent metrics and recommendations
        """
        self.orchestrator.finalize_agent_execution(
            agent_id=subagent_id,
            success=success,
            total_time_ms=total_time_ms,
            tool_count=tool_count,
        )

        # Get improvement suggestions for this subagent
        suggestions = self.orchestrator.get_agent_improvement_suggestions(subagent_id)

        # Clean up
        self.active_subagents.pop(subagent_id, None)

        return {
            "subagent_id": subagent_id,
            "success": success,
            "total_time_ms": total_time_ms,
            "tools_used": tool_count,
            "improvement_suggestions": suggestions,
            "summary": summary,
        }


# Singleton monitor
_monitor: Optional[SubagentMonitor] = None


def get_subagent_monitor() -> SubagentMonitor:
    """Get or create singleton subagent monitor."""
    global _monitor
    if _monitor is None:
        _monitor = SubagentMonitor()
    return _monitor
