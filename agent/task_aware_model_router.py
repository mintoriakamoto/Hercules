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
        logger.debug("Analyzing task for routing: %s (tools=%d)", task_description[:80], available_tools)

        # Determine task complexity using extended reasoning engine
        try:
            complexity = self.reasoning_engine.analyze_task_complexity(
                task_description,
                available_tools=available_tools,
                time_budget_seconds=30.0,
            )
            logger.debug("Task complexity analyzed: %s", complexity.value)
        except Exception as e:
            logger.warning(
                "Complexity analysis failed; using moderate complexity fallback: %s",
                str(e)[:100],
            )
            complexity = ReasoningComplexity.MODERATE

        # Determine task category by keyword matching
        category = self._categorize_task(task_description)
        logger.debug("Task category identified: %s", category.value if category else "none")

        # Find best matching routing rule
        # Security rules get highest priority to override complexity-based routing
        best_rule: Optional[ModelRoutingRule] = None
        best_match_score = 0.0

        logger.debug("Evaluating %d routing rules for task", len(self.routing_rules))

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
                    logger.debug(
                        "Rule keyword match: category=%s, keywords_matched=%d, boost=%.2f%%",
                        rule.category.value if rule.category else "any",
                        keyword_matches,
                        (boost * min(keyword_matches, 3) * 100),
                    )

            if match_score > best_match_score:
                best_match_score = match_score
                best_rule = rule
                logger.debug(
                    "New best rule: complexity=%s, category=%s, tier=%s, score=%.3f",
                    rule.complexity.value,
                    rule.category.value if rule.category else "any",
                    rule.tier.value,
                    match_score,
                )

        # Use best rule or fall back to balanced tier
        if best_rule:
            tier = best_rule.tier
            confidence = best_rule.confidence
            cat_str = category.value if category else ""
            reasoning = f"Matched rule for {complexity.value} {cat_str}"
            logger.info(
                "Task routed by rule match: tier=%s, confidence=%.2f, rule_complexity=%s, rule_category=%s",
                tier.value,
                confidence,
                best_rule.complexity.value,
                best_rule.category.value if best_rule.category else "any",
            )
        else:
            tier = ModelTier.BALANCED
            confidence = 0.5
            reasoning = (
                f"No rule matched; using default balanced tier "
                f"for {complexity.value}"
            )
            logger.info(
                "Task routed to default: tier=%s, reason=no_rule_match, complexity=%s",
                tier.value,
                complexity.value,
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
            selected = models[0]
            logger.debug(
                "Model selected from tier: tier=%s, model=%s, available=%d",
                tier.value,
                selected,
                len(models),
            )
            return selected
        logger.warning("No models available for tier: %s", tier.value)
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

# Default fallback model if routing completely fails
_FALLBACK_MODEL = "claude-sonnet-5"


def _validate_routing_result(decision: RoutingDecision) -> RoutingDecision:
    """Validate routing result and apply fallbacks if needed.

    Ensures that routing always produces a valid, usable result even if
    some components fail (e.g., model not available in tier).

    Args:
        decision: The routing decision to validate

    Returns:
        A valid routing decision with fallback model if needed
    """
    # Ensure we always have a model
    if not decision.recommended_model:
        decision.recommended_model = _FALLBACK_MODEL
        logger.warning(
            "Routing result had no model; using fallback: %s (tier=%s)",
            _FALLBACK_MODEL,
            decision.recommended_tier.value,
        )

    # Ensure confidence is in valid range
    if not (0.0 <= decision.confidence <= 1.0):
        old_confidence = decision.confidence
        decision.confidence = max(0.0, min(1.0, decision.confidence))
        logger.warning(
            "Routing confidence out of range [0-1]: %.2f → %.2f",
            old_confidence,
            decision.confidence,
        )

    # Ensure cost savings is in valid range
    if decision.cost_savings_estimate is not None:
        if not (0.0 <= decision.cost_savings_estimate <= 100.0):
            old_savings = decision.cost_savings_estimate
            decision.cost_savings_estimate = max(0.0, min(100.0, decision.cost_savings_estimate))
            logger.warning(
                "Routing cost savings out of range [0-100%%]: %.1f → %.1f",
                old_savings,
                decision.cost_savings_estimate,
            )

    return decision


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
    Includes comprehensive error handling and fallback strategies.

    Args:
        task_description: Description of the task
        available_tools: Number of available tools

    Returns:
        Tuple of (recommended_model_id, routing_decision)

    Raises:
        No exceptions — always returns a valid fallback result.
    """
    try:
        # Validate input
        if not task_description or not isinstance(task_description, str):
            logger.warning(
                "Invalid task description for routing; using fallback model. "
                "task_type=%s",
                type(task_description).__name__,
            )
            return _FALLBACK_MODEL, RoutingDecision(
                recommended_tier=ModelTier.BALANCED,
                recommended_model=_FALLBACK_MODEL,
                complexity=ReasoningComplexity.MODERATE,
                confidence=0.5,
                reasoning="Invalid task description; using fallback",
            )

        if available_tools < 0:
            logger.warning("Negative available_tools: %d; clamping to 0", available_tools)
            available_tools = 0

        router = get_model_router()
        decision = router.analyze_task(task_description, available_tools)

        # Validate and fix any issues with the decision
        decision = _validate_routing_result(decision)

        model = decision.recommended_model or _FALLBACK_MODEL

        logger.info(
            "Task routing decision: task=%s... → model=%s (tier=%s, complexity=%s, category=%s, "
            "confidence=%.2f, savings=%.1f%%)",
            task_description[:60],
            model,
            decision.recommended_tier.value,
            decision.complexity.value,
            decision.category.value if decision.category else "uncategorized",
            decision.confidence,
            decision.cost_savings_estimate or 0.0,
        )

        if decision.cost_savings_estimate and decision.cost_savings_estimate > 0:
            logger.info(
                "Routing cost optimization: estimated %.1f%% cost savings by using %s "
                "(reasoning: %s)",
                decision.cost_savings_estimate,
                model,
                decision.reasoning,
            )

        return model, decision

    except Exception as e:
        logger.exception(
            "Task routing failed with exception; using fallback model %s: %s",
            _FALLBACK_MODEL,
            str(e)[:200],
        )
        # Return safe fallback
        return _FALLBACK_MODEL, RoutingDecision(
            recommended_tier=ModelTier.BALANCED,
            recommended_model=_FALLBACK_MODEL,
            complexity=ReasoningComplexity.MODERATE,
            confidence=0.3,
            reasoning=f"Routing failed: {str(e)[:100]}; using fallback",
        )
