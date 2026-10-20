"""Task-Aware Agent Design - Customize agents for specific task classes.

Before delegating a task, analyzes the task to determine optimal agent
configuration. Uses task similarity matching, resource estimation, and
constraint optimization to design purpose-built subagents.

Pattern:
  1. Parse task description
  2. Infer task type and complexity
  3. Lookup similar successful tasks in registry
  4. Design optimized agent variant
  5. Spawn subagent with tailored configuration
  6. Monitor task execution
  7. Record result for future learning
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TaskAnalysis:
    """Analysis of task requirements and difficulty."""

    task_type: str  # "coding", "analysis", "planning", "research", "creative", "multi"
    complexity_score: float  # 0.0-1.0 estimated difficulty
    estimated_tokens: int  # Expected tokens needed
    estimated_iterations: int  # Expected tool call iterations
    required_tools: List[str]
    required_models: List[str]
    parallelizable: bool  # Can subtasks run in parallel?
    requires_verification: bool  # Does output need verification?
    estimated_time_minutes: float


@dataclass(frozen=True)
class AgentBlueprint:
    """Complete specification for custom-designed agent."""

    task_type: str
    model: str
    toolsets: List[str]
    system_prompt_template: str
    max_iterations: int
    max_tokens: Optional[int]
    max_spawn_depth: int
    max_concurrent_children: int
    delegation_strategy: str
    resource_limits: Dict[str, Any]
    estimated_success_rate: float
    estimated_cost_tokens: float
    reasoning: str


class TaskDesigner:
    """Designs agents optimized for specific task classes."""

    def __init__(
        self,
        registry: Optional[Any] = None,
        introspection: Optional[Any] = None,
        design: Optional[Any] = None,
    ):
        """Initialize designer.

        Args:
            registry: Architecture learning registry.
            introspection: Agent introspection API.
            design: Agent design API.
        """
        self.registry = registry
        self.introspection = introspection
        self.design = design

    def design_agent_for_task(
        self, task_description: str
    ) -> AgentBlueprint:
        """Design custom agent for specific task.

        Analyzes task and creates optimized agent configuration.

        Args:
            task_description: Full task description/prompt.

        Returns:
            AgentBlueprint with complete agent specification.
        """
        # Analyze task
        analysis = self._analyze_task(task_description)

        # Check registry for similar successful tasks
        registry_suggestion = None
        if self.registry:
            registry_suggestion = self.registry.lookup_successful_architecture(
                task_description
            )

        # Design agent variant
        if self.design and self.introspection:
            variant = self.design.propose_agent_variant(
                goal=task_description,
                context={"analysis": asdict(analysis)},
                budget={"max_tokens": analysis.estimated_tokens},
            )

            # Convert variant to blueprint
            blueprint = self._variant_to_blueprint(variant, analysis)
        else:
            # Fallback: basic blueprint from analysis
            blueprint = self._blueprint_from_analysis(analysis)

        # Apply registry suggestions if better
        if registry_suggestion:
            blueprint = self._merge_registry_suggestion(
                blueprint, registry_suggestion, analysis
            )

        logger.info(
            "Designed agent for task type %s: model=%s, "
            "complexity=%.2f, est_success_rate=%.2f%%",
            analysis.task_type,
            blueprint.model,
            analysis.complexity_score,
            blueprint.estimated_success_rate * 100,
        )

        return blueprint

    def apply_blueprint_to_agent_config(
        self, blueprint: AgentBlueprint, base_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply blueprint to agent configuration.

        Args:
            blueprint: Agent design blueprint.
            base_config: Base agent configuration to modify.

        Returns:
            Modified agent configuration.
        """
        config = base_config.copy()

        # Apply blueprint values
        config["model"] = blueprint.model
        config["enabled_toolsets"] = blueprint.toolsets
        config["max_iterations"] = blueprint.max_iterations
        config["max_tokens"] = blueprint.max_tokens
        config["system_prompt_delta"] = blueprint.system_prompt_template

        # Apply delegation settings
        config["max_spawn_depth"] = blueprint.max_spawn_depth
        config["max_concurrent_children"] = blueprint.max_concurrent_children

        return config

    # --- Internal helpers ---

    def _analyze_task(self, task: str) -> TaskAnalysis:
        """Analyze task to determine requirements.

        Args:
            task: Task description.

        Returns:
            TaskAnalysis with requirements and estimates.
        """
        task_type = self._infer_task_type(task)
        complexity = self._estimate_complexity(task)
        tokens = self._estimate_tokens(task, complexity)
        iterations = self._estimate_iterations(task, complexity)
        tools = self._infer_required_tools(task)
        models = self._infer_required_models(task, complexity)
        parallelizable = self._is_parallelizable(task)
        needs_verification = self._needs_verification(task)
        time_estimate = self._estimate_time(task, complexity)

        return TaskAnalysis(
            task_type=task_type,
            complexity_score=complexity,
            estimated_tokens=tokens,
            estimated_iterations=iterations,
            required_tools=tools,
            required_models=models,
            parallelizable=parallelizable,
            requires_verification=needs_verification,
            estimated_time_minutes=time_estimate,
        )

    def _infer_task_type(self, task: str) -> str:
        """Infer primary task type."""
        task_lower = task.lower()

        if any(
            w in task_lower
            for w in ["code", "python", "write", "implement", "debug"]
        ):
            return "coding"

        if any(
            w in task_lower
            for w in ["analyze", "review", "evaluate", "compare"]
        ):
            return "analysis"

        if any(
            w in task_lower
            for w in ["design", "plan", "architecture", "strategy"]
        ):
            return "planning"

        if any(
            w in task_lower
            for w in ["research", "search", "find", "investigate"]
        ):
            return "research"

        if any(
            w in task_lower
            for w in ["create", "write", "generate", "compose"]
        ):
            return "creative"

        if any(
            w in task_lower
            for w in ["parallel", "batch", "multi", "concurrent"]
        ):
            return "multi"

        return "general"

    def _estimate_complexity(self, task: str) -> float:
        """Estimate task complexity 0.0-1.0."""
        score = 0.3  # Base

        # Length indicates complexity
        task_len = len(task)
        if task_len > 2000:
            score += 0.2
        if task_len > 5000:
            score += 0.2

        # Keywords
        complexity_keywords = [
            "complex",
            "design",
            "architecture",
            "novel",
            "proof",
        ]
        if any(kw in task.lower() for kw in complexity_keywords):
            score += 0.2

        difficulty_keywords = [
            "expert",
            "research",
            "advanced",
            "challenging",
        ]
        if any(kw in task.lower() for kw in difficulty_keywords):
            score += 0.15

        return min(1.0, score)

    def _estimate_tokens(self, task: str, complexity: float) -> int:
        """Estimate tokens needed for task."""
        base = 4096

        # Adjust for length
        task_len = len(task)
        if task_len > 2000:
            base = 6000
        if task_len > 5000:
            base = 8000

        # Adjust for complexity
        if complexity > 0.7:
            base = max(base, 6000)

        # Adjust for task type
        if "code" in task.lower():
            base = max(base, 5000)
        if "design" in task.lower():
            base = max(base, 5000)

        return base

    def _estimate_iterations(self, task: str, complexity: float) -> int:
        """Estimate tool call iterations."""
        base = 10

        if complexity > 0.7:
            base = 20
        elif complexity > 0.5:
            base = 15

        if "parallel" in task.lower():
            base += 5

        return min(base, 50)

    def _infer_required_tools(self, task: str) -> List[str]:
        """Infer required tools from task."""
        tools = []

        if any(w in task.lower() for w in ["python", "code", "script"]):
            tools.append("bash")
        if any(w in task.lower() for w in ["file", "save", "read"]):
            tools.append("file_operations")
        if any(w in task.lower() for w in ["web", "search", "url"]):
            tools.append("browser")
        if any(w in task.lower() for w in ["github", "git", "pr"]):
            tools.append("github")

        return tools or ["core"]

    def _infer_required_models(self, task: str, complexity: float) -> List[str]:
        """Infer required models."""
        models = []

        if complexity > 0.8 or "reasoning" in task.lower():
            models.append("claude-opus-4-20250514")
        elif complexity > 0.5:
            models.append("claude-opus-4-20250514")
        else:
            models.append("claude-haiku-4-5-20251001")

        return models

    def _is_parallelizable(self, task: str) -> bool:
        """Check if task can be parallelized."""
        keywords = ["parallel", "batch", "multiple", "concurrent"]
        return any(kw in task.lower() for kw in keywords)

    def _needs_verification(self, task: str) -> bool:
        """Check if task output needs verification."""
        keywords = ["verify", "test", "check", "proof"]
        return any(kw in task.lower() for kw in keywords)

    def _estimate_time(self, task: str, complexity: float) -> float:
        """Estimate execution time in minutes."""
        base = 5.0
        base += complexity * 15  # Complexity adds 0-15 minutes
        if len(task) > 2000:
            base += 5
        return base

    def _variant_to_blueprint(
        self, variant: Any, analysis: TaskAnalysis
    ) -> AgentBlueprint:
        """Convert design variant to blueprint.

        Args:
            variant: AgentVariant from design API.
            analysis: TaskAnalysis.

        Returns:
            AgentBlueprint.
        """
        return AgentBlueprint(
            task_type=analysis.task_type,
            model=variant.model,
            toolsets=variant.toolsets,
            system_prompt_template=variant.system_prompt_delta,
            max_iterations=variant.max_iterations,
            max_tokens=variant.max_tokens,
            max_spawn_depth=(
                1 if variant.delegation_strategy == "narrow" else 0
            ),
            max_concurrent_children=(
                3 if variant.delegation_strategy in ["broad", "recursive"] else 1
            ),
            delegation_strategy=variant.delegation_strategy,
            resource_limits=variant.resource_budget,
            estimated_success_rate=0.75,  # Would improve with history
            estimated_cost_tokens=float(variant.max_tokens or 4096),
            reasoning=variant.reasoning,
        )

    def _blueprint_from_analysis(self, analysis: TaskAnalysis) -> AgentBlueprint:
        """Create basic blueprint from analysis.

        Args:
            analysis: TaskAnalysis.

        Returns:
            Basic AgentBlueprint.
        """
        model = (
            "claude-opus-4-20250514"
            if analysis.complexity_score > 0.6
            else "claude-haiku-4-5-20251001"
        )

        return AgentBlueprint(
            task_type=analysis.task_type,
            model=model,
            toolsets=analysis.required_tools,
            system_prompt_template=f"Focus on: {analysis.task_type} task",
            max_iterations=analysis.estimated_iterations,
            max_tokens=analysis.estimated_tokens,
            max_spawn_depth=0,
            max_concurrent_children=1,
            delegation_strategy="none",
            resource_limits={"max_tokens": analysis.estimated_tokens},
            estimated_success_rate=0.7,
            estimated_cost_tokens=float(analysis.estimated_tokens),
            reasoning=f"Basic design for {analysis.task_type} (complexity {analysis.complexity_score:.2f})",
        )

    def _merge_registry_suggestion(
        self,
        blueprint: AgentBlueprint,
        registry_config: Dict[str, Any],
        analysis: TaskAnalysis,
    ) -> AgentBlueprint:
        """Merge registry suggestion into blueprint if better.

        Args:
            blueprint: Current blueprint.
            registry_config: Suggested config from registry.
            analysis: Task analysis.

        Returns:
            Potentially updated blueprint.
        """
        # Use registry config if it matches task type
        registry_type = registry_config.get("task_type")
        if registry_type and registry_type == analysis.task_type:
            logger.info(
                "Merging registry suggestion for task type %s",
                registry_type,
            )

            return AgentBlueprint(
                task_type=analysis.task_type,
                model=registry_config.get("model", blueprint.model),
                toolsets=registry_config.get(
                    "enabled_toolsets", blueprint.toolsets
                ),
                system_prompt_template=blueprint.system_prompt_template,
                max_iterations=registry_config.get(
                    "max_iterations", blueprint.max_iterations
                ),
                max_tokens=registry_config.get(
                    "max_tokens", blueprint.max_tokens
                ),
                max_spawn_depth=blueprint.max_spawn_depth,
                max_concurrent_children=blueprint.max_concurrent_children,
                delegation_strategy=blueprint.delegation_strategy,
                resource_limits=blueprint.resource_limits,
                estimated_success_rate=0.8,  # Higher confidence
                estimated_cost_tokens=blueprint.estimated_cost_tokens,
                reasoning=(
                    f"Based on similar successful tasks in registry. "
                    f"Original reasoning: {blueprint.reasoning}"
                ),
            )

        return blueprint
