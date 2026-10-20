"""Agent Design API - Propose optimized agent architectures.

This module enables agents to design better versions of themselves by
proposing optimized configurations based on task requirements, performance
history, and resource constraints.

Key capabilities:
  - Propose agent variants optimized for specific tasks
  - Generate system prompt variants for task classes
  - Compose minimal toolsets based on requirements
  - Estimate resource requirements
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentVariant:
    """Proposed agent configuration variant."""

    model: str
    toolsets: List[str]
    system_prompt_delta: str  # Partial prompt to inject/modify
    delegation_strategy: str  # "none", "narrow", "broad", "recursive"
    max_iterations: int
    max_tokens: Optional[int]
    resource_budget: Dict[str, Any]  # token budget, time, etc.
    reasoning_config: Optional[Dict[str, Any]] = None
    reasoning: str = ""  # Designer's reasoning about this variant

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    def merge_into_config(self, base_config: Dict[str, Any]) -> Dict[str, Any]:
        """Merge this variant into a base agent config."""
        config = base_config.copy()
        config["model"] = self.model
        config["enabled_toolsets"] = self.toolsets
        config["max_iterations"] = self.max_iterations
        config["max_tokens"] = self.max_tokens

        # Merge delegation strategy into config
        if self.delegation_strategy == "narrow":
            config["max_spawn_depth"] = 1
            config["max_concurrent_children"] = 1
        elif self.delegation_strategy == "broad":
            config["max_spawn_depth"] = 2
            config["max_concurrent_children"] = 4
        elif self.delegation_strategy == "recursive":
            config["max_spawn_depth"] = 3
            config["max_concurrent_children"] = 3

        return config


@dataclass(frozen=True)
class ToolsetComposition:
    """Result of toolset composition."""

    selected_toolsets: List[str]
    reasoning: str
    estimated_token_cost: int  # For schemas
    coverage_percentage: float  # % of requirements met
    alternatives: List[str]  # Alternative toolsets if needed


class Design:
    """Generate optimized agent designs."""

    def __init__(self, agent: Any, registry: Optional[Any] = None):
        """Initialize designer.

        Args:
            agent: Reference agent to use as base.
            registry: Optional architecture registry for lookup.
        """
        self.agent = agent
        self.registry = registry

    def propose_agent_variant(
        self,
        goal: str,
        context: Dict[str, Any],
        budget: Dict[str, Any],
    ) -> AgentVariant:
        """Propose optimized agent for specific goal.

        Analyzes goal requirements, checks registry for similar successful
        tasks, and proposes an optimized agent configuration.

        Args:
            goal: Task description or objective.
            context: Additional context (parent config, constraints, etc.)
            budget: Resource budget {"max_tokens": N, "max_time_seconds": N}

        Returns:
            AgentVariant with proposed configuration.
        """
        # Check registry for similar successful tasks
        suggested_config = None
        if self.registry:
            suggested_config = self.registry.lookup_successful_architecture(goal)

        # Extract requirements from goal
        requires_reasoning = self._goal_requires_reasoning(goal)
        requires_tools = self._extract_goal_tools(goal)
        requires_context = self._estimate_context_needed(goal)

        # Choose model based on requirements
        model = self._propose_model(
            goal=goal,
            requires_reasoning=requires_reasoning,
            base_model=getattr(self.agent, "model", "claude-opus"),
        )

        # Compose toolset
        toolsets = self._compose_toolset(requires_tools, budget)

        # Determine delegation strategy
        delegation_strategy = self._propose_delegation_strategy(goal, context)

        # Generate prompt delta
        prompt_delta = self.generate_system_prompt_variant(
            task=goal, constraints={"focus": self._extract_focus(goal)}
        )

        # Estimate resource needs
        max_iterations = self._estimate_iterations(goal)
        max_tokens = self._estimate_tokens(goal, requires_context)

        # Validate against budget
        resource_budget = self._validate_resource_budget(
            estimated_tokens=max_tokens,
            budget=budget,
        )

        reasoning_config = None
        if requires_reasoning:
            reasoning_config = {"enabled": True, "max_thinking_tokens": 8000}

        reasoning_type = (
            "complex task, needs extended thinking"
            if requires_reasoning
            else "straightforward"
        )
        reasoning = (
            f"Proposed {model} model for {goal[:50]}... "
            f"with toolsets {toolsets}. "
            f"Reasoning: {reasoning_type}"
        )

        return AgentVariant(
            model=model,
            toolsets=toolsets,
            system_prompt_delta=prompt_delta,
            delegation_strategy=delegation_strategy,
            max_iterations=max_iterations,
            max_tokens=max_tokens,
            resource_budget=resource_budget,
            reasoning_config=reasoning_config,
            reasoning=reasoning,
        )

    def generate_system_prompt_variant(
        self, task: str, constraints: Dict[str, Any]
    ) -> str:
        """Generate system prompt variant optimized for task.

        Creates a specialized prompt that focuses on the task requirements.

        Args:
            task: Task description.
            constraints: Additional constraints/guidance.

        Returns:
            Prompt delta to inject into base prompt.
        """
        focus = constraints.get("focus", task[:100])
        task_type = self._infer_task_type(task)

        # Build specialized prompt section
        prompt_sections = [
            f"# Task Focus: {focus}",
            "",
            "## Approach",
        ]

        if task_type == "coding":
            prompt_sections.extend([
                "- Write clean, well-documented code",
                "- Include error handling and edge cases",
                "- Test thoroughly before concluding",
                "- Prioritize correctness over cleverness",
            ])
        elif task_type == "analysis":
            prompt_sections.extend([
                "- Structure analysis logically",
                "- Support claims with evidence",
                "- Consider multiple perspectives",
                "- Highlight key findings and uncertainties",
            ])
        elif task_type == "planning":
            prompt_sections.extend([
                "- Break down into concrete steps",
                "- Identify dependencies and risks",
                "- Estimate resource requirements",
                "- Provide fallback approaches",
            ])
        else:
            prompt_sections.extend([
                "- Think step by step",
                "- Verify assumptions before proceeding",
                "- Ask clarifying questions if needed",
                "- Provide clear reasoning",
            ])

        prompt_sections.append("")
        prompt_sections.append("## Success Criteria")
        prompt_sections.extend([
            f"- Complete the task: {task[:80]}",
            "- Provide clear output",
            "- Explain key decisions",
        ])

        return "\n".join(prompt_sections)

    def compose_toolset(
        self, task_requirements: List[str], cost_budget: Dict[str, Any]
    ) -> ToolsetComposition:
        """Assemble minimal toolset for requirements.

        Selects minimal set of toolsets that cover task requirements
        while staying within cost budget.

        Args:
            task_requirements: List of required capabilities.
            cost_budget: Budget constraints.

        Returns:
            ToolsetComposition with selected toolsets.
        """
        # Map requirements to toolsets
        req_to_toolset = {
            "file_ops": "files",
            "bash": "terminal",
            "python": "code",
            "web": "browser",
            "github": "version_control",
            "api": "http_client",
        }

        selected = []
        coverage = 0.0

        for req in task_requirements:
            toolset = req_to_toolset.get(req, req)
            if toolset not in selected:
                selected.append(toolset)
                coverage += 1.0 / len(task_requirements)

        # Add base toolsets if missing
        if "core" not in selected:
            selected.insert(0, "core")

        # Estimate token cost for schemas
        token_cost = self._estimate_toolset_schema_cost(selected)

        # Check if within budget
        budget_tokens = cost_budget.get("max_tokens", 100000)
        if token_cost > budget_tokens * 0.2:  # Schemas should be <20% of budget
            logger.warning(
                "Toolset composition %s exceeds schema budget", selected
            )

        alternatives = self._suggest_alternatives(selected)

        reasoning = (
            f"Selected {len(selected)} toolsets to cover "
            f"{int(coverage*100)}% of requirements"
        )

        return ToolsetComposition(
            selected_toolsets=selected,
            reasoning=reasoning,
            estimated_token_cost=token_cost,
            coverage_percentage=coverage,
            alternatives=alternatives,
        )

    # --- Internal helpers ---

    def _goal_requires_reasoning(self, goal: str) -> bool:
        """Check if goal needs extended reasoning."""
        keywords = [
            "design",
            "architecture",
            "proof",
            "complex",
            "novel",
            "research",
        ]
        return any(kw in goal.lower() for kw in keywords)

    def _extract_goal_tools(self, goal: str) -> List[str]:
        """Extract implied tool requirements from goal."""
        requirements = []
        if any(
            w in goal.lower() for w in ["code", "python", "script", "write"]
        ):
            requirements.append("code")
        if any(
            w in goal.lower() for w in ["file", "directory", "read", "save"]
        ):
            requirements.append("file_ops")
        if any(
            w in goal.lower() for w in ["bash", "shell", "command", "run"]
        ):
            requirements.append("bash")
        if any(
            w in goal.lower() for w in ["web", "search", "url", "fetch"]
        ):
            requirements.append("web")
        if any(
            w in goal.lower() for w in ["github", "git", "repo", "pr"]
        ):
            requirements.append("github")
        return requirements

    def _estimate_context_needed(self, goal: str) -> int:
        """Estimate context tokens needed."""
        if len(goal) > 1000:
            return 8000
        elif any(w in goal.lower() for w in ["analyze", "summarize", "review"]):
            return 6000
        return 4000

    def _propose_model(
        self, goal: str, requires_reasoning: bool, base_model: str
    ) -> str:
        """Choose best model for goal."""
        if requires_reasoning:
            return "claude-opus-4-20250514"  # Supports extended thinking

        if "complex" in goal.lower() or "design" in goal.lower():
            return "claude-opus-4-20250514"

        # Check if smaller model might work
        if len(goal) < 200 and "simple" in goal.lower():
            return "claude-haiku-4-5-20251001"

        return base_model

    def _compose_toolset(
        self, requires_tools: List[str], budget: Dict[str, Any]
    ) -> List[str]:
        """Select toolsets for requirements."""
        composition = self.compose_toolset(requires_tools, budget)
        return composition.selected_toolsets

    def _propose_delegation_strategy(
        self, goal: str, context: Dict[str, Any]
    ) -> str:
        """Choose delegation strategy."""
        if "parallel" in goal.lower() or "batch" in goal.lower():
            return "broad"
        if "recursive" in goal.lower():
            return "recursive"
        if "subtask" in goal.lower():
            return "narrow"
        return "none"

    def _extract_focus(self, goal: str) -> str:
        """Extract main focus from goal."""
        return goal.split(".")[0].split("\n")[0][:100]

    def _estimate_iterations(self, goal: str) -> int:
        """Estimate max iterations needed."""
        if "complex" in goal.lower():
            return 30
        elif "simple" in goal.lower():
            return 5
        return 15

    def _estimate_tokens(self, goal: str, context_needed: int) -> int:
        """Estimate max_tokens needed."""
        base = 4096
        if context_needed > 6000:
            base = 8192
        if "code" in goal.lower():
            base = max(base, 6000)
        return base

    def _validate_resource_budget(
        self, estimated_tokens: int, budget: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate against resource budget."""
        max_budget = budget.get("max_tokens", 100000)
        if estimated_tokens > max_budget:
            logger.warning(
                "Estimated tokens %d exceed budget %d",
                estimated_tokens,
                max_budget,
            )
        return {"max_tokens": min(estimated_tokens, max_budget)}

    def _infer_task_type(self, task: str) -> str:
        """Infer task type from description."""
        if any(
            w in task.lower() for w in ["code", "python", "write", "script"]
        ):
            return "coding"
        if any(w in task.lower() for w in ["analyze", "review", "check"]):
            return "analysis"
        if any(w in task.lower() for w in ["plan", "design", "architecture"]):
            return "planning"
        return "general"

    def _estimate_toolset_schema_cost(self, toolsets: List[str]) -> int:
        """Rough estimate of tokens for tool schemas."""
        # Average ~300 tokens per toolset schema
        return len(toolsets) * 300

    def _suggest_alternatives(self, selected: List[str]) -> List[str]:
        """Suggest alternative toolsets if main ones unavailable."""
        alternatives = []
        if "terminal" in selected and "code" not in selected:
            alternatives.append("code")
        if "browser" in selected:
            alternatives.append("http_client")
        return alternatives
