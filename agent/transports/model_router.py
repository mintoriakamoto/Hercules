"""Main model router for intelligent task routing in conversation loop.

Integrates all routing components:
1. Task complexity classification
2. Model selection by tier
3. Speculative execution
4. Ensemble voting for critical operations

Entry point: route_request() is called from conversation_loop.py before API call.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from agent.extended_reasoning import ReasoningComplexity
from agent.routing.task_classifier import classify_request_complexity, ComplexityScore
from agent.routing_types import ModelTier

logger = logging.getLogger(__name__)


@dataclass
class RoutingDecision:
    """Decision made by the router."""

    primary_model: str
    fallback_model: Optional[str] = None
    tier: ModelTier = ModelTier.BALANCED
    complexity_score: int = 50
    confidence: float = 0.5
    should_speculate: bool = False
    should_ensemble: bool = False
    reasoning: str = ""
    cost_estimate: float = 1.0  # Relative cost (1.0 = baseline)


class ConversationLoopModelRouter:
    """Routes models for requests in the conversation loop."""

    def __init__(self):
        """Initialize the router."""
        self.model_tier_map = self._build_model_tier_map()
        self.routing_history: List[Dict[str, Any]] = []
        self._last_decision_info = None

    def route_request(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Any]] = None,
        agent_config: Optional[Dict[str, Any]] = None
    ) -> RoutingDecision:
        """
        Route a request to the best model.

        This is the main entry point called from conversation_loop.py
        before each API call.

        Args:
            messages: Conversation messages in API format
            tools: Available tools (optional)
            agent_config: Agent configuration (optional, contains current model/provider)

        Returns:
            RoutingDecision with recommended model and metadata
        """
        start_time = time.time()

        # Classify complexity
        complexity_score = classify_request_complexity(
            messages,
            tools,
            len(tools) if tools else 0
        )

        # Select tier based on complexity
        tier = self._select_tier(complexity_score)

        # Select model from tier
        primary_model = self._select_model(tier, agent_config)
        fallback_model = self._select_fallback_model(tier)

        # Determine if we should use speculative execution
        should_speculate = self._should_use_speculative(
            complexity_score, agent_config
        )

        # Determine if we should use ensemble voting
        should_ensemble = self._should_use_ensemble(
            complexity_score, agent_config
        )

        # Estimate relative cost
        cost_estimate = self._estimate_cost(tier, complexity_score)

        # Build reasoning
        reasoning = self._build_reasoning(
            complexity_score, tier, primary_model, should_speculate, should_ensemble
        )

        decision = RoutingDecision(
            primary_model=primary_model,
            fallback_model=fallback_model,
            tier=tier,
            complexity_score=complexity_score.score,
            confidence=complexity_score.confidence,
            should_speculate=should_speculate,
            should_ensemble=should_ensemble,
            reasoning=reasoning,
            cost_estimate=cost_estimate
        )

        # Store in history
        self.routing_history.append({
            "timestamp": time.time(),
            "complexity_score": complexity_score.score,
            "tier": tier.value,
            "model": primary_model,
            "speculate": should_speculate,
            "ensemble": should_ensemble,
            "time_ms": (time.time() - start_time) * 1000
        })

        self._last_decision_info = decision

        logger.info(
            "Routing decision: complexity=%d, tier=%s, model=%s (confidence=%.2f), "
            "speculate=%s, ensemble=%s",
            complexity_score.score,
            tier.value,
            primary_model,
            complexity_score.confidence,
            should_speculate,
            should_ensemble
        )

        return decision

    def _select_tier(self, complexity: ComplexityScore) -> ModelTier:
        """Select model tier based on complexity score."""
        score = complexity.score

        if score < 30:
            return ModelTier.FAST_CHEAP
        elif score < 70:
            return ModelTier.BALANCED
        elif score < 85:
            return ModelTier.CAPABLE
        else:
            return ModelTier.EXTENDED

    def _select_model(
        self,
        tier: ModelTier,
        agent_config: Optional[Dict[str, Any]]
    ) -> str:
        """Select specific model from tier."""
        models = self.model_tier_map.get(tier, [])

        if not models:
            logger.warning("No models available for tier %s; using fallback", tier.value)
            return "claude-sonnet-5"  # Safe fallback

        # Try to use a model that's different from current (for variety)
        current_model = None
        if agent_config:
            current_model = agent_config.get("model")

        # Return first available model that's not current
        for model in models:
            if model != current_model:
                return model

        # If all are current, return first
        return models[0]

    def _select_fallback_model(self, tier: ModelTier) -> str:
        """Select fallback model (typically from higher tier)."""
        fallback_tier = ModelTier.BALANCED
        if tier == ModelTier.CAPABLE or tier == ModelTier.EXTENDED:
            fallback_tier = ModelTier.CAPABLE
        elif tier == ModelTier.FAST_CHEAP:
            fallback_tier = ModelTier.BALANCED

        models = self.model_tier_map.get(fallback_tier, [])
        return models[0] if models else "claude-sonnet-5"

    def _should_use_speculative(
        self,
        complexity: ComplexityScore,
        agent_config: Optional[Dict[str, Any]]
    ) -> bool:
        """Determine if speculative execution should be used."""
        # Use speculative for moderate+ complexity (good ROI)
        if complexity.score >= 40:
            return True

        # Enable based on agent config (if enabled)
        if agent_config and agent_config.get("enable_speculative"):
            return True

        return False

    def _should_use_ensemble(
        self,
        complexity: ComplexityScore,
        agent_config: Optional[Dict[str, Any]]
    ) -> bool:
        """Determine if ensemble voting should be used."""
        # Use ensemble for complex/critical operations only
        if complexity.score >= 75:
            return True

        # Check for high-stakes categories
        category = complexity.indicators.get("dominant_keywords")
        if category in ["complex", "critical"]:
            return True

        # Enable based on agent config
        if agent_config and agent_config.get("enable_ensemble"):
            return True

        return False

    def _estimate_cost(self, tier: ModelTier, complexity: ComplexityScore) -> float:
        """Estimate relative cost compared to baseline (Sonnet)."""
        tier_costs = {
            ModelTier.FAST_CHEAP: 0.15,   # Haiku is ~15% of Sonnet cost
            ModelTier.BALANCED: 1.0,      # Sonnet baseline
            ModelTier.CAPABLE: 2.5,       # Opus ~2.5x Sonnet
            ModelTier.EXTENDED: 4.0,      # Extended thinking ~4x Sonnet
        }
        return tier_costs.get(tier, 1.0)

    def _build_reasoning(
        self,
        complexity: ComplexityScore,
        tier: ModelTier,
        model: str,
        speculate: bool,
        ensemble: bool
    ) -> str:
        """Build human-readable reasoning for routing decision."""
        parts = [
            f"Complexity {complexity.score}/100 ({complexity.category})",
            f"Tier: {tier.value}",
            f"Model: {model}"
        ]

        if complexity.indicators.get("has_code"):
            parts.append("code detected")

        if speculate:
            parts.append("speculative execution enabled")

        if ensemble:
            parts.append("ensemble voting enabled")

        return "; ".join(parts)

    def _build_model_tier_map(self) -> Dict[ModelTier, List[str]]:
        """Build mapping of tiers to available models."""
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
                "o1-preview",
            ],
            ModelTier.EXTENDED: [
                "claude-opus-5-extended",  # hypothetical
                "o1",
            ],
        }

    def get_routing_metrics(self) -> Dict[str, Any]:
        """Get routing metrics summary."""
        if not self.routing_history:
            return {
                "total_routed": 0,
                "by_tier": {},
                "by_complexity": {}
            }

        by_tier = {}
        by_complexity = {}

        for entry in self.routing_history:
            tier = entry.get("tier", "unknown")
            by_tier[tier] = by_tier.get(tier, 0) + 1

            complexity_range = "simple"
            score = entry.get("complexity_score", 50)
            if score >= 70:
                complexity_range = "complex"
            elif score >= 30:
                complexity_range = "moderate"

            by_complexity[complexity_range] = by_complexity.get(complexity_range, 0) + 1

        return {
            "total_routed": len(self.routing_history),
            "by_tier": by_tier,
            "by_complexity": by_complexity,
            "speculative_enabled_pct": (
                sum(1 for e in self.routing_history if e.get("speculate"))
                / max(1, len(self.routing_history)) * 100
            ),
            "ensemble_enabled_pct": (
                sum(1 for e in self.routing_history if e.get("ensemble"))
                / max(1, len(self.routing_history)) * 100
            ),
        }

    def get_routing_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent routing history."""
        return self.routing_history[-limit:]


# Singleton instance
_router: Optional[ConversationLoopModelRouter] = None


def get_model_router() -> ConversationLoopModelRouter:
    """Get or create the model router."""
    global _router
    if _router is None:
        _router = ConversationLoopModelRouter()
    return _router


def route_request(
    messages: List[Dict[str, Any]],
    tools: Optional[List[Any]] = None,
    agent_config: Optional[Dict[str, Any]] = None
) -> RoutingDecision:
    """
    Route a request using the singleton router.

    This is the primary entry point from conversation_loop.py.

    Args:
        messages: Conversation messages
        tools: Available tools
        agent_config: Agent configuration

    Returns:
        RoutingDecision with recommended model and metadata
    """
    router = get_model_router()
    return router.route_request(messages, tools, agent_config)
