"""Integration layer - Connect metaprogramming to agent runtime.

Provides high-level APIs for integrating the architecture-as-code system
with the main agent loop and delegation system.

Main entry points:
  - setup_metaprogramming(agent): Initialize all systems
  - record_task_execution(agent, task, result): Log execution
  - design_subagent(parent, task): Create optimized child agent
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from agent.meta.introspection import Introspection
from agent.meta.design import Design
from agent.meta.registry import ArchitectureRegistry, ArchitectureRecord
from agent.meta.emergence import EmergenceTracker, AgentGenealogy, EmergenceEvent
from agent.delegation.self_modify import SelfModificationManager
from agent.planning.task_designer import TaskDesigner

logger = logging.getLogger(__name__)


class MetaprogrammingSystem:
    """Unified interface to architecture-as-code system."""

    def __init__(
        self,
        agent: Any,
        registry_db: Optional[str] = None,
        emergence_db: Optional[str] = None,
    ):
        """Initialize metaprogramming system.

        Args:
            agent: The AIAgent instance.
            registry_db: Path to architecture registry database.
            emergence_db: Path to emergence tracker database.
        """
        self.agent = agent
        self.introspection = Introspection(agent)
        self.design = Design(agent, registry=None)  # Will set after registry
        self.registry = ArchitectureRegistry(db_path=registry_db)
        self.design.registry = self.registry  # Set registry now
        self.emergence = EmergenceTracker(db_path=emergence_db)
        self.self_modifier = SelfModificationManager(agent)
        self.task_designer = TaskDesigner(
            registry=self.registry,
            introspection=self.introspection,
            design=self.design,
        )

        logger.info("Initialized MetaprogrammingSystem for agent %s",
                   getattr(agent, 'session_id', 'unknown'))

    def record_task_execution(
        self,
        task_description: str,
        success: bool,
        cost_tokens: int,
        iterations_used: int,
        tools_used: List[str],
        execution_time_seconds: float,
    ) -> str:
        """Record task execution for learning.

        Args:
            task_description: What was the task.
            success: Did task succeed.
            cost_tokens: Tokens consumed.
            iterations_used: Tool call iterations.
            tools_used: Which tools were called.
            execution_time_seconds: How long it took.

        Returns:
            task_id for tracking.
        """
        task_id = str(uuid.uuid4())
        model = getattr(self.agent, "model", "unknown")

        # Analyze task type
        from agent.planning.task_designer import TaskDesigner as TD

        td = TaskDesigner()
        analysis = td._analyze_task(task_description)

        # Record in registry
        record = ArchitectureRecord(
            task_id=task_id,
            task_description=task_description,
            task_type=analysis.task_type,
            agent_config=self.introspection.get_self_config().to_dict(),
            success=success,
            success_rate=1.0 if success else 0.0,
            avg_cost_tokens=float(cost_tokens),
            iterations_used=iterations_used,
            model_used=model,
            toolsets_used=tools_used,
            timestamp=time.time(),
            designer_agent_id=getattr(self.agent, "parent_session_id", None),
        )

        self.registry.record_task_result(record)

        logger.info(
            "Recorded task %s: success=%s, cost=%d tokens, "
            "iterations=%d, time=%.1fs",
            task_id,
            success,
            cost_tokens,
            iterations_used,
            execution_time_seconds,
        )

        return task_id

    def design_subagent_config(
        self, task_description: str
    ) -> Dict[str, Any]:
        """Design optimized configuration for subagent.

        Analyzes task and returns agent configuration optimized for it.

        Args:
            task_description: Task the subagent will handle.

        Returns:
            Agent configuration dict ready to pass to subagent spawn.
        """
        blueprint = self.task_designer.design_agent_for_task(
            task_description
        )

        # Get current agent config as base
        base_config = {
            "model": getattr(self.agent, "model", "claude-opus-4-20250514"),
            "enabled_toolsets": getattr(self.agent, "enabled_toolsets", []),
            "max_iterations": getattr(self.agent, "max_iterations", 30),
            "max_tokens": getattr(self.agent, "max_tokens", None),
        }

        # Apply blueprint
        return self.task_designer.apply_blueprint_to_agent_config(
            blueprint, base_config
        )

    def detect_capability_gaps(
        self, task: str
    ) -> List[Dict[str, Any]]:
        """Identify capability gaps for task.

        Args:
            task: Task description.

        Returns:
            List of gap descriptions with recommended solutions.
        """
        gaps = self.introspection.estimate_capability_gap(task)

        return [
            {
                "type": gap.gap_type,
                "description": gap.description,
                "recommendation": gap.recommended_solution,
                "priority": gap.priority,
                "impact": gap.estimated_impact,
            }
            for gap in gaps
        ]

    def propose_parent_improvement(
        self,
        task_description: str,
        delta_config: Dict[str, Any],
        expected_improvement: Dict[str, float],
        justification: str,
    ) -> str:
        """Subagent proposes improvement to parent.

        Child agent identifies beneficial configuration changes and
        proposes them to parent for adoption.

        Args:
            task_description: Task being completed.
            delta_config: Configuration changes.
            expected_improvement: Expected metric improvements.
            justification: Why this change helps.

        Returns:
            proposal_id for tracking.
        """
        child_id = getattr(self.agent, "session_id", "unknown")
        parent_id = getattr(self.agent, "parent_session_id", None)

        if not parent_id:
            logger.warning(
                "Cannot propose modification: no parent_session_id"
            )
            return ""

        proposal_id = self.self_modifier.propose_self_modification(
            child_agent_id=child_id,
            task_description=task_description,
            delta_config=delta_config,
            expected_improvement=expected_improvement,
            justification=justification,
        )

        logger.info(
            "Child %s proposed modification to parent %s: %s",
            child_id,
            parent_id,
            proposal_id,
        )

        return proposal_id

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get agent performance metrics.

        Returns:
            Dict with success rates, costs, iterations, etc.
        """
        stats = self.registry.get_statistics()

        return {
            "total_tasks": stats.get("total_records", 0),
            "successful_tasks": stats.get("successful_records", 0),
            "overall_success_rate": stats.get("overall_success_rate", 0.0),
            "avg_success_rate": stats.get("avg_success_rate", 0.0),
            "avg_cost_tokens": stats.get("avg_cost_tokens", 0.0),
            "avg_iterations": stats.get("avg_iterations", 0.0),
            "top_models": stats.get("top_models", []),
        }

    def get_agent_genealogy(self) -> Dict[str, Any]:
        """Get agent's lineage information.

        Returns:
            Dict with agent genealogy and emergence info.
        """
        agent_id = getattr(self.agent, "session_id", None)
        if not agent_id:
            return {}

        lineage = self.emergence.get_agent_lineage(agent_id)

        return {
            "agent_id": agent_id,
            "generation": lineage[0].generation if lineage else 0,
            "parent_id": lineage[0].parent_agent_id if lineage else None,
            "lineage_depth": len(lineage),
            "capabilities_gained": (
                lineage[0].capabilities_gained if lineage else []
            ),
            "emergence_score": lineage[0].emergence_score if lineage else 0.0,
        }

    def export_state(self) -> Dict[str, Any]:
        """Export metaprogramming state for inspection.

        Returns:
            Complete state snapshot.
        """
        return {
            "agent_config": self.introspection.get_self_config().to_dict(),
            "capabilities": self.introspection.query_self_capabilities().to_dict(),
            "performance_metrics": self.get_performance_metrics(),
            "genealogy": self.get_agent_genealogy(),
            "pending_modifications": {
                k: v.to_dict()
                for k, v in self.self_modifier.pending_proposals.items()
            },
            "applied_modifications": len(
                self.self_modifier.applied_modifications
            ),
        }


def setup_metaprogramming(
    agent: Any,
    registry_db: Optional[str] = None,
    emergence_db: Optional[str] = None,
) -> MetaprogrammingSystem:
    """Initialize metaprogramming system for agent.

    Call this during agent initialization to enable architecture-as-code.

    Args:
        agent: The AIAgent instance.
        registry_db: Optional custom registry database path.
        emergence_db: Optional custom emergence database path.

    Returns:
        Initialized MetaprogrammingSystem.
    """
    return MetaprogrammingSystem(
        agent,
        registry_db=registry_db,
        emergence_db=emergence_db,
    )


def record_task_execution(
    metaprogramming: MetaprogrammingSystem,
    task_description: str,
    success: bool,
    cost_tokens: int,
    iterations_used: int,
    tools_used: List[str],
    execution_time_seconds: float,
) -> str:
    """Record task execution for learning.

    Call this after a significant task completes.

    Args:
        metaprogramming: MetaprogrammingSystem instance.
        task_description: What was the task.
        success: Did it succeed.
        cost_tokens: Tokens consumed.
        iterations_used: Tool call count.
        tools_used: Tools that were used.
        execution_time_seconds: Execution time.

    Returns:
        task_id for tracking.
    """
    return metaprogramming.record_task_execution(
        task_description=task_description,
        success=success,
        cost_tokens=cost_tokens,
        iterations_used=iterations_used,
        tools_used=tools_used,
        execution_time_seconds=execution_time_seconds,
    )


def design_subagent(
    metaprogramming: MetaprogrammingSystem,
    task_description: str,
) -> Dict[str, Any]:
    """Design optimized subagent for task.

    Call before spawning a delegation subagent.

    Args:
        metaprogramming: MetaprogrammingSystem instance.
        task_description: Task the subagent will handle.

    Returns:
        Agent configuration ready for subagent spawn.
    """
    return metaprogramming.design_subagent_config(task_description)
