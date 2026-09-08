"""Task-aware model routing for delegation.

Automatically selects the most appropriate model for a delegated task based on:
- Task complexity (simple, moderate, complex)
- Cost constraints
- Required capabilities
- Configured routing rules

This enables cost optimization (using cheaper models for simple tasks) and
capability matching (using more capable models for complex reasoning).
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from agent.extended_reasoning import (
    ReasoningComplexity,
    get_reasoning_engine,
)

logger = logging.getLogger(__name__)


class ModelTier(str, Enum):
    """Model capability tiers for task routing."""

    FAST_CHEAP = "fast_cheap"  # e.g., GPT-4o mini, Claude Haiku — speed/cost focused
    BALANCED = "balanced"  # e.g., Claude Sonnet, GPT-4o — general purpose
    CAPABLE = "capable"  # e.g., Claude Opus, o1 — advanced reasoning
    EXTENDED = "extended"  # e.g., o1-pro — extended thinking, research


class TaskCategory(str, Enum):
    """Task categories for routing decisions."""

    READ = "read"  # Information retrieval, file reading
    ANALYZE = "analyze"  # Analysis, summarization, simple classification
    CODE = "code"  # Programming, code generation, debugging
    REASONING = "reasoning"  # Complex reasoning, planning, design
    RESEARCH = "research"  # Deep research, exploration, comprehensive analysis
    SECURITY = "security"  # Security testing, vulnerability analysis


@dataclass
class ModelRoutingRule:
    """A rule that maps task characteristics to recommended models."""

    complexity: ReasoningComplexity
    category: Optional[TaskCategory] = None
    tier: ModelTier = ModelTier.BALANCED
    min_cost_per_mtok: Optional[float] = None  # Min cost threshold
    max_cost_per_mtok: Optional[float] = None  # Max cost threshold
    keywords: List[str] = field(default_factory=list)  # Keywords triggering rule
    confidence: float = 0.8  # Confidence score


@dataclass
class RoutingDecision:
    """Result of routing analysis for a task."""

    recommended_tier: ModelTier
    recommended_model: Optional[str] = None
    complexity: ReasoningComplexity = ReasoningComplexity.MODERATE
    category: Optional[TaskCategory] = None
    confidence: float = 0.5
    reasoning: str = ""
    cost_savings_estimate: Optional[float] = None


class TaskAwareModelRouter:
    """Routes tasks to appropriate models based on complexity and requirements."""

    def __init__(self):
        """Initialize the model router."""
        self.reasoning_engine = get_reasoning_engine()
        self.routing_rules = self._build_default_rules()
        self.model_tier_mapping = self._build_model_tier_mapping()

    def _build_default_rules(self) -> List[ModelRoutingRule]:
        """Build default routing rules mapping complexity to model tiers."""
        return [
            # Simple/read tasks → fast/cheap models
            ModelRoutingRule(
                complexity=ReasoningComplexity.SIMPLE,
                tier=ModelTier.FAST_CHEAP,
                keywords=["read", "list", "get", "find", "extract", "check"],
                confidence=0.9,
            ),
            # Moderate analysis → balanced models
            ModelRoutingRule(
                complexity=ReasoningComplexity.MODERATE,
                tier=ModelTier.BALANCED,
                keywords=["analyze", "summarize", "describe", "classify"],
                confidence=0.85,
            ),
            # Complex reasoning → capable models
            ModelRoutingRule(
                complexity=ReasoningComplexity.COMPLEX,
                tier=ModelTier.CAPABLE,
                keywords=[
                    "design",
                    "plan",
                    "diagnose",
                    "optimize",
                    "security",
                    "vulnerability",
                ],
                confidence=0.85,
            ),
            # Critical/research → extended thinking
            ModelRoutingRule(
                complexity=ReasoningComplexity.CRITICAL,
                tier=ModelTier.EXTENDED,
                keywords=["research", "explore", "comprehensive", "deep"],
                confidence=0.8,
            ),
            # Security-specific → capable minimum
            ModelRoutingRule(
                complexity=ReasoningComplexity.COMPLEX,
                category=TaskCategory.SECURITY,
                tier=ModelTier.CAPABLE,
                keywords=["penetr", "exploit", "vuln", "attack", "defense"],
                confidence=0.95,
            ),
        ]

    def _build_model_tier_mapping(self) -> Dict[ModelTier, List[str]]:
        """Map model tiers to available model IDs.

        In production, this would read from config.yaml or model registry.
        For now, we use typical model examples.
        """
        return {
            ModelTier.FAST_CHEAP: [
                "claude-haiku-4-5-20251001",
                "gpt-4o-mini",
            ],
            ModelTier.BALANCED: [
                "claude-sonnet-5",
                "gpt-4o",
            ],
            ModelTier.CAPABLE: [
                "claude-opus-5",
                "o1",
            ],
            ModelTier.EXTENDED: [
                "o1-pro",
                "claude-opus-5-extended",  # hypothetical extended thinking
            ],
        }

    def analyze_task(
        self, task_description: str, available_tools: int = 0
    ) -> RoutingDecision:
        """Analyze a task and recommend a model tier and optionally a specific model.

        Args:
            task_description: Description of the task to be performed
            available_tools: Number of tools available to the agent

        Returns:
            RoutingDecision with recommended model tier and optional specific model
        """
        # Determine task complexity using extended reasoning engine
        complexity = self.reasoning_engine.analyze_task_complexity(
            task_description,
            available_tools=available_tools,
            time_budget_seconds=30.0,
        )

        # Determine task category by keyword matching
        category = self._categorize_task(task_description)

        # Find best matching routing rule
        # Security rules get highest priority to override complexity-based routing
        best_rule: Optional[ModelRoutingRule] = None
        best_match_score = 0.0

        for rule in self.routing_rules:
            # Score based on complexity match
            if rule.complexity == complexity:
                match_score = rule.confidence * 1.0
            else:
                # Partial credit for adjacent complexity levels
                match_score = rule.confidence * 0.5

            # Boost score if category matches
            # Security category gets extra boost to override other routing
            if category and rule.category == category:
                boost_factor = 1.5 if category == TaskCategory.SECURITY else 1.2
                match_score *= boost_factor

            # Boost score if keywords match
            if rule.keywords:
                keyword_matches = sum(
                    1 for kw in rule.keywords if kw.lower() in task_description.lower()
                )
                if keyword_matches > 0:
                    # Security keywords get higher boost
                    is_security_rule = rule.category == TaskCategory.SECURITY
                    boost = 0.15 if is_security_rule else 0.1
                    match_score *= 1.0 + (boost * min(keyword_matches, 3))

            if match_score > best_match_score:
                best_match_score = match_score
                best_rule = rule

        # Use best rule or fall back to balanced tier
        if best_rule:
            tier = best_rule.tier
            confidence = best_rule.confidence
            cat_str = category.value if category else ""
            reasoning = f"Matched rule for {complexity.value} {cat_str}"
        else:
            tier = ModelTier.BALANCED
            confidence = 0.5
            reasoning = (
                f"No rule matched; using default balanced tier "
                f"for {complexity.value}"
            )

        # Select specific model from tier if available
        recommended_model = self._select_model_from_tier(tier)

        # Estimate cost savings if routing to cheaper tier
        cost_savings = self._estimate_cost_savings(complexity, tier)

        return RoutingDecision(
            recommended_tier=tier,
            recommended_model=recommended_model,
            complexity=complexity,
            category=category,
            confidence=confidence,
            reasoning=reasoning,
            cost_savings_estimate=cost_savings,
        )

    def _categorize_task(self, task_description: str) -> Optional[TaskCategory]:
        """Categorize a task by keyword matching.

        Security category takes priority over others to avoid misclassification.
        """
        task_lower = task_description.lower()

        # Security first (highest priority to avoid misclassification with "test")
        security_keywords = [
            "security",
            "penetr",
            "exploit",
            "vuln",
            "attack",
            "defense",
        ]
        if any(kw in task_lower for kw in security_keywords):
            return TaskCategory.SECURITY

        category_keywords = {
            TaskCategory.READ: ["read", "list", "get", "find", "retrieve", "fetch"],
            TaskCategory.ANALYZE: ["analyze", "summary", "classify"],
            TaskCategory.CODE: ["code", "write", "implement", "debug"],
            TaskCategory.REASONING: ["reason", "think", "plan", "design", "trade-off"],
            TaskCategory.RESEARCH: [
                "research",
                "explore",
                "investigate",
                "comprehensive",
                "deep",
            ],
        }

        for category, keywords in category_keywords.items():
            if any(kw in task_lower for kw in keywords):
                return category

        return None

    def _select_model_from_tier(self, tier: ModelTier) -> Optional[str]:
        """Select a specific model from the given tier.

        In production, this would prefer based on availability, cost, and user config.
        For now, returns the first available model in the tier.
        """
        models = self.model_tier_mapping.get(tier, [])
        if models:
            return models[0]
        return None

    def _estimate_cost_savings(
        self, original_complexity: ReasoningComplexity, new_tier: ModelTier
    ) -> Optional[float]:
        """Estimate cost savings from routing to a different model tier.

        Returns percentage savings (0-100), or None if no savings expected.
        """
        # Simple heuristic: estimate cost based on tier
        complexity_base_cost = {
            ReasoningComplexity.SIMPLE: 1.0,
            ReasoningComplexity.MODERATE: 2.0,
            ReasoningComplexity.COMPLEX: 5.0,
            ReasoningComplexity.CRITICAL: 10.0,
        }

        tier_multiplier = {
            ModelTier.FAST_CHEAP: 0.1,
            ModelTier.BALANCED: 1.0,
            ModelTier.CAPABLE: 2.0,
            ModelTier.EXTENDED: 5.0,
        }

        original_cost = complexity_base_cost.get(original_complexity, 2.0) * 1.0
        tier_mult = tier_multiplier.get(new_tier, 1.0)
        new_cost = complexity_base_cost.get(original_complexity, 2.0) * tier_mult

        if original_cost > new_cost:
            savings_pct = ((original_cost - new_cost) / original_cost) * 100
            return max(0, min(100, savings_pct))

        return None


# Singleton instance
_router: Optional[TaskAwareModelRouter] = None


def get_model_router() -> TaskAwareModelRouter:
    """Get or create the task-aware model router singleton."""
    global _router
    if _router is None:
        _router = TaskAwareModelRouter()
    return _router


def route_task_to_model(
    task_description: str, available_tools: int = 0
) -> Tuple[str, RoutingDecision]:
    """Route a task description to a recommended model.

    This is the primary entry point for task-aware model routing.

    Args:
        task_description: Description of the task
        available_tools: Number of available tools

    Returns:
        Tuple of (recommended_model_id, routing_decision)
    """
    router = get_model_router()
    decision = router.analyze_task(task_description, available_tools)

    model = decision.recommended_model or "claude-sonnet-5"

    logger.debug(
        "Task routing: %s -> %s (tier=%s, confidence=%.2f)",
        task_description[:50],
        model,
        decision.recommended_tier.value,
        decision.confidence,
    )

    if decision.cost_savings_estimate and decision.cost_savings_estimate > 0:
        logger.info(
            "Estimated cost savings: %.1f%% by routing to %s",
            decision.cost_savings_estimate,
            model,
        )

    return model, decision
