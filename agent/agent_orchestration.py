"""Agent orchestration layer for CORAL self-improvement and extended reasoning.

Integrates self-improvement and reasoning capabilities into the main agent loop,
subagent delegation, and multi-agent coordination.

This module provides:
- Performance tracking hooks for the conversation loop
- Reasoning-informed task decomposition for delegation
- Improvement propagation to subagents and parallel tasks
- Multi-agent orchestration with confidence-based strategies
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Callable

from agent.self_improvement_coral import get_improvement_engine
from agent.extended_reasoning import get_reasoning_engine, DecisionContext, ReasoningComplexity
from hercules_constants import get_hercules_home

logger = logging.getLogger(__name__)


@dataclass
class AgentExecutionContext:
    """Context for an agent execution (main or subagent)."""
    agent_id: str
    task_description: str
    complexity: ReasoningComplexity
    parent_agent_id: Optional[str] = None
    depth: int = 0  # 0 = main, 1+ = subagent
    time_budget_seconds: float = 30.0
    domain: str = "general"
    recommended_tools: List[str] = None
    reasoning_chain: Optional[Dict[str, Any]] = None


@dataclass
class AgentToolExecution:
    """Record of a tool execution by an agent."""
    agent_id: str
    tool_name: str
    success: bool
    latency_ms: float
    timestamp: int
    error_type: Optional[str] = None
    result_size: int = 0
    context: Dict[str, Any] = None


class AgentOrchestrator:
    """Manages orchestration of main agent and subagents with self-improvement and reasoning."""

    def __init__(self):
        self.improvement_engine = get_improvement_engine()
        self.reasoning_engine = get_reasoning_engine()
        self.active_contexts: Dict[str, AgentExecutionContext] = {}
        self._execution_history: List[AgentToolExecution] = []

    def initialize_agent_context(
        self,
        agent_id: str,
        task_description: str,
        parent_agent_id: Optional[str] = None,
        depth: int = 0,
        time_budget_seconds: float = 30.0,
        domain: str = "general",
    ) -> AgentExecutionContext:
        """Initialize execution context for an agent.

        Args:
            agent_id: Unique identifier for this agent instance
            task_description: What the agent is being asked to do
            parent_agent_id: ID of parent agent (if subagent)
            depth: Nesting depth (0=main, 1+=subagent)
            time_budget_seconds: Time available for execution
            domain: Task domain (general, web, file_system, security, data)

        Returns:
            AgentExecutionContext with reasoning and tool recommendations
        """
        # Analyze task complexity and build reasoning
        complexity = self.reasoning_engine.analyze_task_complexity(
            task_description,
            available_tools=20,  # Assume ~20 tools available
            time_budget_seconds=time_budget_seconds,
        )

        # For complex tasks, build full reasoning chain
        reasoning_chain = None
        recommended_tools = []

        if complexity != ReasoningComplexity.SIMPLE or depth > 0:
            context = DecisionContext(
                task_description=task_description,
                user_intent=f"Execute as {'subagent' if parent_agent_id else 'main agent'} at depth {depth}",
                available_tools=[],  # Will be filled by conversation loop
                time_budget_seconds=time_budget_seconds,
                domain=domain,
                complexity=complexity,
            )
            reasoning = self.reasoning_engine.build_reasoning_chain(context)
            reasoning_chain = reasoning.to_dict()
            recommended_tools = reasoning.recommended_tool_sequence

        context = AgentExecutionContext(
            agent_id=agent_id,
            task_description=task_description,
            complexity=complexity,
            parent_agent_id=parent_agent_id,
            depth=depth,
            time_budget_seconds=time_budget_seconds,
            domain=domain,
            recommended_tools=recommended_tools,
            reasoning_chain=reasoning_chain,
        )

        self.active_contexts[agent_id] = context
        return context

    def record_tool_execution(
        self,
        agent_id: str,
        tool_name: str,
        success: bool,
        latency_ms: float,
        error_type: Optional[str] = None,
        result_size: int = 0,
    ) -> None:
        """Record execution of a tool by an agent.

        Args:
            agent_id: Agent that executed the tool
            tool_name: Name of the tool
            success: Whether execution succeeded
            latency_ms: Execution time
            error_type: Type of error (if failed)
            result_size: Size of result in bytes
        """
        execution = AgentToolExecution(
            agent_id=agent_id,
            tool_name=tool_name,
            success=success,
            latency_ms=latency_ms,
            timestamp=int(time.time()),
            error_type=error_type,
            result_size=result_size,
            context={"depth": self.active_contexts.get(agent_id, AgentExecutionContext("", "")).depth},
        )

        self._execution_history.append(execution)

        # Record in CORAL improvement engine
        self.improvement_engine.record_execution(
            skill_name=tool_name,
            success=success,
            latency_ms=latency_ms,
            context={
                "agent_id": agent_id,
                "domain": self.active_contexts.get(agent_id, AgentExecutionContext("", "")).domain,
            },
        )

    def get_tool_recommendations(
        self,
        agent_id: str,
        task_description: str,
        available_tools: List[str],
    ) -> List[tuple[str, float]]:
        """Get recommended tools for a task, ranked by relevance.

        Args:
            agent_id: Agent requesting recommendations
            task_description: What the agent needs to do
            available_tools: Tools available to this agent

        Returns:
            List of (tool_name, relevance_score) tuples, sorted by relevance
        """
        scored = []

        for tool in available_tools:
            result = self.reasoning_engine.score_tool_selection(
                task_description=task_description,
                tool_name=tool,
            )
            if result.get("recommended", False):
                scored.append((tool, result.get("relevance_score", 0.0)))

        # Sort by relevance descending
        return sorted(scored, key=lambda x: x[1], reverse=True)

    def plan_delegation_strategy(
        self,
        parent_agent_id: str,
        num_subagents: int,
        tasks: List[str],
    ) -> Dict[str, Any]:
        """Plan how to decompose work across subagents.

        Uses extended reasoning to determine:
        - Optimal number of parallel subagents
        - How to partition tasks
        - Tool assignment per subagent
        - Monitoring strategy

        Args:
            parent_agent_id: ID of parent agent doing delegation
            num_subagents: Desired number of subagents
            tasks: List of tasks to delegate

        Returns:
            Dictionary with delegation plan
        """
        parent_context = self.active_contexts.get(parent_agent_id)

        plan = {
            "parent_agent_id": parent_agent_id,
            "num_subagents": min(num_subagents, len(tasks)),
            "subagent_tasks": [],
            "monitoring_strategy": "adaptive",
            "estimated_total_time_ms": 0,
        }

        # Simple round-robin distribution
        for i, task in enumerate(tasks):
            subagent_idx = i % plan["num_subagents"]
            plan["subagent_tasks"].append({
                "subagent_id": f"{parent_agent_id}_sub_{subagent_idx}",
                "task": task,
                "index": i,
                "priority": i == 0,  # First task gets priority
            })

        return plan

    def handle_tool_failure(
        self,
        agent_id: str,
        failed_tool: str,
        failure_reason: str,
        available_tools: List[str],
        original_plan: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Generate recovery strategy when a tool fails.

        Args:
            agent_id: Agent that encountered failure
            failed_tool: Tool that failed
            failure_reason: Why it failed
            available_tools: Tools still available
            original_plan: Original tool sequence (if any)

        Returns:
            Recovery strategy with fallback tools and approach
        """
        fallback = self.reasoning_engine.generate_fallback_strategy(
            original_approach=original_plan or [failed_tool],
            failure_reason=failure_reason,
            available_tools=available_tools,
        )

        return {
            "agent_id": agent_id,
            "failed_tool": failed_tool,
            "failure_reason": failure_reason,
            "fallback_sequence": fallback,
            "estimated_recovery_time_ms": 500 * len(fallback),  # Rough estimate
            "should_retry_immediately": "rate_limit" not in failure_reason.lower(),
            "recommendation": "Use fallback sequence" if fallback != [failed_tool] else "Investigate tool",
        }

    def finalize_agent_execution(
        self,
        agent_id: str,
        success: bool,
        total_time_ms: float,
        tool_count: int,
    ) -> None:
        """Record completion of agent execution.

        Args:
            agent_id: Agent that completed
            success: Whether overall task succeeded
            total_time_ms: Total execution time
            tool_count: Number of tools used
        """
        context = self.active_contexts.pop(agent_id, None)

        if context and context.depth == 0:  # Only track main agent completions
            # Update overall agent performance
            self.improvement_engine.record_execution(
                skill_name="agent_main",
                success=success,
                latency_ms=total_time_ms,
                context={
                    "tools_used": tool_count,
                    "domain": context.domain,
                },
            )

    def get_agent_improvement_suggestions(
        self,
        agent_id: str,
    ) -> List[Dict[str, Any]]:
        """Get improvement suggestions for an agent's recent performance.

        Args:
            agent_id: Agent to analyze

        Returns:
            List of improvement suggestions
        """
        # Find recent executions for this agent
        recent = [e for e in self._execution_history if e.agent_id == agent_id][-10:]

        if not recent:
            return []

        # Analyze tool performance
        suggestions = []
        tool_stats: Dict[str, Dict[str, Any]] = {}

        for execution in recent:
            if execution.tool_name not in tool_stats:
                tool_stats[execution.tool_name] = {
                    "count": 0,
                    "success": 0,
                    "total_latency_ms": 0,
                }

            stats = tool_stats[execution.tool_name]
            stats["count"] += 1
            if execution.success:
                stats["success"] += 1
            stats["total_latency_ms"] += execution.latency_ms

        # Generate suggestions
        for tool, stats in tool_stats.items():
            success_rate = stats["success"] / stats["count"]
            avg_latency = stats["total_latency_ms"] / stats["count"]

            if success_rate < 0.7:
                suggestions.append({
                    "tool": tool,
                    "type": "reliability",
                    "issue": f"Low success rate: {success_rate*100:.0f}%",
                    "recommendation": f"Add error handling or fallback for {tool}",
                })

            if avg_latency > 1000:  # >1s
                suggestions.append({
                    "tool": tool,
                    "type": "performance",
                    "issue": f"High latency: {avg_latency:.0f}ms",
                    "recommendation": f"Optimize {tool} or add caching",
                })

        return suggestions

    def get_orchestration_metrics(self) -> Dict[str, Any]:
        """Get metrics about agent orchestration and improvements.

        Returns:
            Dictionary with orchestration metrics
        """
        return {
            "active_agents": len(self.active_contexts),
            "total_executions": len(self._execution_history),
            "improvement_stats": self.improvement_engine.get_improvement_stats(),
            "avg_execution_latency_ms": (
                sum(e.latency_ms for e in self._execution_history) / len(self._execution_history)
                if self._execution_history else 0
            ),
        }


# Singleton orchestrator
_orchestrator: Optional[AgentOrchestrator] = None


def get_agent_orchestrator() -> AgentOrchestrator:
    """Get or create singleton agent orchestrator."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
    return _orchestrator
