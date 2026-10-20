"""Agent Introspection API - Self-awareness for autonomous agents.

Provides mechanisms for an agent to understand its own configuration,
capabilities, performance metrics, and capability gaps.

This enables agents to:
  - Reason about what they can and cannot do
  - Identify capability gaps for specific tasks
  - Propose improvements to their architecture
  - Communicate their constraints to designers
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentConfig:
    """Complete agent configuration snapshot."""

    model: str
    toolsets: List[str]
    system_prompt: str
    max_tokens: Optional[int]
    max_iterations: int
    delegation_config: Dict[str, Any]
    performance_metrics: Dict[str, Any]
    agent_id: Optional[str] = None
    created_at: Optional[str] = None
    parent_agent_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentConfig":
        """Create from dictionary."""
        return cls(**data)

    def get_resource_profile(self) -> Dict[str, Any]:
        """Get resource allocation profile."""
        return {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "max_iterations": self.max_iterations,
            "num_toolsets": len(self.toolsets),
            "delegation_depth": self.delegation_config.get(
                "max_spawn_depth", 0
            ),
            "delegation_width": self.delegation_config.get(
                "max_concurrent_children", 1
            ),
        }


@dataclass(frozen=True)
class CapabilityProfile:
    """Snapshot of agent capabilities."""

    tools: List[str]
    models: List[str]
    max_tokens: Optional[int]
    success_rate: float
    avg_cost_per_task: float
    supported_task_types: List[str]
    unsupported_task_types: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class TaskPerformance:
    """Performance metrics for a single task."""

    task_id: str
    task_description: str
    success: bool
    cost_tokens: int
    iterations_used: int
    tools_used: List[str]
    execution_time_seconds: float
    timestamp: str
    model_used: str
    error_if_failed: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class CapabilityGap:
    """Identified gap in agent capabilities."""

    gap_type: str  # "model", "tool", "reasoning", "memory", "delegation"
    description: str
    task_requiring_gap: str
    recommended_solution: str
    estimated_impact: float  # 0.0-1.0 impact on success rate
    priority: int  # 1-5, higher is more critical


class Introspection:
    """Query agent configuration and performance."""

    def __init__(self, agent: Any):
        """Initialize with agent reference.

        Args:
            agent: The AIAgent instance to introspect.
        """
        self.agent = agent

    def get_self_config(self) -> AgentConfig:
        """Get complete agent configuration.

        Returns:
            AgentConfig with all settings and performance metrics.
        """
        # Get basic configuration
        model = getattr(self.agent, "model", "unknown")
        enabled_toolsets = getattr(self.agent, "enabled_toolsets", []) or []
        max_tokens = getattr(self.agent, "max_tokens", None)
        max_iterations = getattr(self.agent, "max_iterations", 90)
        session_id = getattr(self.agent, "session_id", None)

        # Get system prompt (may be modified)
        system_prompt = getattr(self.agent, "system_prompt", "")

        # Get delegation configuration
        delegation_config = self._get_delegation_config()

        # Get performance metrics
        performance_metrics = self._get_performance_metrics()

        # Get parent info
        parent_session_id = getattr(self.agent, "parent_session_id", None)

        return AgentConfig(
            model=model,
            toolsets=list(enabled_toolsets),
            system_prompt=system_prompt[:500],  # Truncate for size
            max_tokens=max_tokens,
            max_iterations=max_iterations,
            delegation_config=delegation_config,
            performance_metrics=performance_metrics,
            agent_id=session_id,
            created_at=datetime.utcnow().isoformat(),
            parent_agent_id=parent_session_id,
        )

    def query_self_capabilities(self) -> CapabilityProfile:
        """Get agent capabilities profile.

        Returns:
            CapabilityProfile with tools, models, success rates, etc.
        """
        # Get tools from registry
        tools = self._get_available_tools()

        # Get model capability
        model = getattr(self.agent, "model", "unknown")
        models = [model]

        # Get performance data
        max_tokens = getattr(self.agent, "max_tokens", None)
        success_rate = self._calculate_success_rate()
        avg_cost = self._calculate_avg_cost()

        # Infer task types from tool availability and history
        supported_tasks = self._infer_supported_task_types(tools)
        unsupported_tasks = self._infer_unsupported_task_types()

        return CapabilityProfile(
            tools=tools,
            models=models,
            max_tokens=max_tokens,
            success_rate=success_rate,
            avg_cost_per_task=avg_cost,
            supported_task_types=supported_tasks,
            unsupported_task_types=unsupported_tasks,
        )

    def get_performance_history(self, limit: int = 100) -> List[TaskPerformance]:
        """Get last N tasks and their performance.

        Args:
            limit: Maximum number of tasks to return.

        Returns:
            List of TaskPerformance records, most recent first.
        """
        # This would query the session database or performance log
        # For now, return empty list as placeholder
        # In production, would integrate with hercules_state.SessionDB
        return []

    def estimate_capability_gap(self, task: str) -> List[CapabilityGap]:
        """Identify capability gaps for a specific task.

        Analyzes task requirements against current agent capabilities.

        Args:
            task: Task description or requirements.

        Returns:
            List of CapabilityGap items ranked by priority.
        """
        gaps: List[CapabilityGap] = []

        # Analyze task for model requirements
        if self._task_requires_extended_thinking(task):
            # Check if model supports it
            model = getattr(self.agent, "model", "")
            if not self._model_supports_extended_thinking(model):
                gaps.append(
                    CapabilityGap(
                        gap_type="model",
                        description="Task requires extended thinking",
                        task_requiring_gap=task[:100],
                        recommended_solution="Switch to model with extended_thinking support (claude-opus)",
                        estimated_impact=0.4,
                        priority=5,
                    )
                )

        # Analyze task for tool requirements
        required_tools = self._extract_tool_requirements(task)
        available_tools = self._get_available_tools()
        missing_tools = [t for t in required_tools if t not in available_tools]

        for tool in missing_tools:
            gaps.append(
                CapabilityGap(
                    gap_type="tool",
                    description=f"Task requires {tool} tool",
                    task_requiring_gap=task[:100],
                    recommended_solution=f"Enable {tool} toolset",
                    estimated_impact=0.3,
                    priority=4,
                )
            )

        # Check memory/context requirements
        if self._task_requires_large_context(task):
            gaps.append(
                CapabilityGap(
                    gap_type="memory",
                    description="Task requires large context window",
                    task_requiring_gap=task[:100],
                    recommended_solution="Increase max_tokens or use compression",
                    estimated_impact=0.25,
                    priority=3,
                )
            )

        # Check delegation needs
        if self._task_requires_delegation(task):
            config = self._get_delegation_config()
            if config.get("max_spawn_depth", 0) == 0:
                gaps.append(
                    CapabilityGap(
                        gap_type="delegation",
                        description="Task requires subagent delegation",
                        task_requiring_gap=task[:100],
                        recommended_solution="Enable delegation with max_spawn_depth > 0",
                        estimated_impact=0.2,
                        priority=2,
                    )
                )

        # Sort by priority
        return sorted(gaps, key=lambda g: -g.priority)

    # --- Internal helpers ---

    def _get_delegation_config(self) -> Dict[str, Any]:
        """Extract delegation configuration from agent."""
        # These would come from the agent's config
        return {
            "max_spawn_depth": getattr(self.agent, "max_spawn_depth", 0),
            "max_concurrent_children": getattr(
                self.agent, "max_concurrent_children", 3
            ),
            "max_total_agents": getattr(self.agent, "max_total_agents", 32),
            "enabled": getattr(self.agent, "delegation_enabled", False),
        }

    def _get_performance_metrics(self) -> Dict[str, Any]:
        """Get aggregate performance metrics."""
        return {
            "total_tasks_completed": 0,
            "successful_tasks": 0,
            "failed_tasks": 0,
            "avg_success_rate": 0.0,
            "total_tokens_used": 0,
            "avg_cost_per_task": 0.0,
        }

    def _get_available_tools(self) -> List[str]:
        """Get list of available tools."""
        tools = []
        try:
            from model_tools import get_tool_definitions

            definitions = get_tool_definitions(
                toolsets=getattr(self.agent, "enabled_toolsets", None)
            )
            if isinstance(definitions, dict):
                tools = list(definitions.keys())
            elif isinstance(definitions, list):
                tools = [t.get("name", "") for t in definitions if t.get("name")]
        except Exception as e:
            logger.warning("Could not get tool definitions: %s", e)
        return tools

    def _calculate_success_rate(self) -> float:
        """Calculate overall success rate from history."""
        # Would integrate with performance database
        return 0.75  # Placeholder

    def _calculate_avg_cost(self) -> float:
        """Calculate average cost per task."""
        # Would integrate with usage tracking
        return 1000.0  # Placeholder (tokens)

    def _infer_supported_task_types(self, tools: List[str]) -> List[str]:
        """Infer which task types are supported by available tools."""
        task_types = []

        if any(
            t in tools
            for t in ["bash", "terminal", "exec", "run_command"]
        ):
            task_types.append("code_execution")
        if any(
            t in tools
            for t in ["read_file", "write_file", "edit_file"]
        ):
            task_types.append("file_operations")
        if any(t in tools for t in ["python_repl", "python_exec"]):
            task_types.append("python_scripting")
        if any(t in tools for t in ["web_search", "browser", "fetch_url"]):
            task_types.append("web_research")
        if any(
            t in tools
            for t in ["create_issue", "list_issues", "push_files", "create_pr"]
        ):
            task_types.append("github_operations")

        return task_types

    def _infer_unsupported_task_types(self) -> List[str]:
        """Infer unsupported task types."""
        # If certain critical tools missing, infer unsupported tasks
        return []

    def _task_requires_extended_thinking(self, task: str) -> bool:
        """Check if task likely requires extended thinking."""
        keywords = [
            "complex",
            "proof",
            "design",
            "architecture",
            "algorithm",
            "research",
        ]
        return any(kw in task.lower() for kw in keywords)

    def _model_supports_extended_thinking(self, model: str) -> bool:
        """Check if model supports extended thinking."""
        supporting_models = [
            "claude-opus",
            "claude-opus-4",
            "gpt-4-turbo",
            "o1",
        ]
        return any(m in model.lower() for m in supporting_models)

    def _extract_tool_requirements(self, task: str) -> List[str]:
        """Extract likely tool requirements from task description."""
        requirements = []

        if any(
            kw in task.lower()
            for kw in ["python", "code", "script", "execute"]
        ):
            requirements.append("bash")
        if any(
            kw in task.lower() for kw in ["file", "directory", "path"]
        ):
            requirements.append("file_operations")
        if any(
            kw in task.lower() for kw in ["search", "web", "url", "fetch"]
        ):
            requirements.append("browser")
        if any(kw in task.lower() for kw in ["github", "pr", "issue"]):
            requirements.append("github")

        return requirements

    def _task_requires_large_context(self, task: str) -> bool:
        """Check if task requires large context."""
        keywords = ["analyze", "summary", "compare", "review", "large"]
        return any(kw in task.lower() for kw in keywords)

    def _task_requires_delegation(self, task: str) -> bool:
        """Check if task would benefit from delegation."""
        keywords = ["parallel", "multiple", "batch", "concurrent"]
        return any(kw in task.lower() for kw in keywords)
