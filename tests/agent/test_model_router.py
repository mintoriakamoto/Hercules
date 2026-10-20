"""Tests for conversation loop model router."""

import pytest

from agent.transports.model_router import (
    ConversationLoopModelRouter,
    RoutingDecision,
    get_model_router,
    route_request,
)
from agent.routing_types import ModelTier


class TestConversationLoopModelRouter:
    """Test the conversation loop model router."""

    def test_router_initialization(self):
        """Test router initialization."""
        router = ConversationLoopModelRouter()
        assert router is not None
        assert router.model_tier_map is not None
        assert len(router.model_tier_map) == 4  # 4 tiers

    def test_route_simple_request(self):
        """Test routing of simple request."""
        router = ConversationLoopModelRouter()
        messages = [{"role": "user", "content": "Read the file"}]

        decision = router.route_request(messages)

        assert isinstance(decision, RoutingDecision)
        assert decision.primary_model is not None
        assert decision.tier == ModelTier.FAST_CHEAP
        assert decision.complexity_score < 35
        assert 0.0 <= decision.confidence <= 1.0

    def test_route_complex_request(self):
        """Test routing of complex request."""
        router = ConversationLoopModelRouter()
        messages = [
            {
                "role": "user",
                "content": "Design a distributed system for handling 1M concurrent users with trade-off analysis"
            }
        ]

        decision = router.route_request(messages)

        assert decision.primary_model is not None
        assert decision.tier in [ModelTier.CAPABLE, ModelTier.EXTENDED, ModelTier.BALANCED]
        assert decision.complexity_score > 40

    def test_tier_selection(self):
        """Test tier selection based on complexity."""
        router = ConversationLoopModelRouter()

        # Simple (0-30)
        simple_messages = [{"role": "user", "content": "Get file list"}]
        simple_decision = router.route_request(simple_messages)
        assert simple_decision.tier == ModelTier.FAST_CHEAP

        # Complex (70+)
        complex_messages = [
            {
                "role": "user",
                "content": "Optimize and design" * 20
            }
        ]
        complex_decision = router.route_request(complex_messages)
        assert complex_decision.tier in [ModelTier.CAPABLE, ModelTier.EXTENDED]

    def test_model_selection_from_tier(self):
        """Test model selection from tier."""
        router = ConversationLoopModelRouter()

        # FAST_CHEAP tier
        fast_model = router._select_model(ModelTier.FAST_CHEAP, None)
        assert fast_model in ["claude-haiku-4-5-20251001", "gpt-4o-mini"]

        # BALANCED tier
        balanced_model = router._select_model(ModelTier.BALANCED, None)
        assert balanced_model in ["claude-sonnet-5", "gpt-4o"]

        # CAPABLE tier
        capable_model = router._select_model(ModelTier.CAPABLE, None)
        assert capable_model in ["claude-opus-5", "o1-preview"]

    def test_fallback_model_selection(self):
        """Test fallback model selection."""
        router = ConversationLoopModelRouter()

        # FAST_CHEAP falls back to BALANCED
        fallback = router._select_fallback_model(ModelTier.FAST_CHEAP)
        assert fallback in ["claude-sonnet-5", "gpt-4o"]

        # CAPABLE falls back to CAPABLE (higher tier)
        fallback = router._select_fallback_model(ModelTier.CAPABLE)
        assert fallback is not None

    def test_speculative_execution_decision(self):
        """Test speculative execution decision."""
        router = ConversationLoopModelRouter()

        # Simple request: no speculative
        simple = router._should_use_speculative(
            type('obj', (), {'score': 20, 'indicators': {}}), None
        )
        assert simple is False

        # Complex request: yes speculative
        complex_score = type('obj', (), {'score': 50, 'indicators': {}})
        should_speculate = router._should_use_speculative(complex_score, None)
        assert should_speculate is True

    def test_ensemble_decision(self):
        """Test ensemble voting decision."""
        router = ConversationLoopModelRouter()

        # Simple request: no ensemble
        simple = router._should_use_ensemble(
            type('obj', (), {'score': 20, 'indicators': {'dominant_keywords': 'simple'}}), None
        )
        assert simple is False

        # Complex request: yes ensemble
        complex_score = type('obj', (), {'score': 80, 'indicators': {'dominant_keywords': 'complex'}})
        should_ensemble = router._should_use_ensemble(complex_score, None)
        assert should_ensemble is True

    def test_cost_estimation(self):
        """Test cost estimation."""
        router = ConversationLoopModelRouter()

        fast_cost = router._estimate_cost(ModelTier.FAST_CHEAP, None)
        assert fast_cost == pytest.approx(0.15)

        balanced_cost = router._estimate_cost(ModelTier.BALANCED, None)
        assert balanced_cost == 1.0

        capable_cost = router._estimate_cost(ModelTier.CAPABLE, None)
        assert capable_cost == pytest.approx(2.5)

    def test_routing_history(self):
        """Test routing history tracking."""
        router = ConversationLoopModelRouter()

        messages = [{"role": "user", "content": "Read file"}]
        router.route_request(messages)

        history = router.get_routing_history(limit=10)
        assert len(history) == 1
        assert "complexity_score" in history[0]
        assert "tier" in history[0]

    def test_routing_metrics(self):
        """Test routing metrics collection."""
        router = ConversationLoopModelRouter()

        messages = [{"role": "user", "content": "Read file"}]
        router.route_request(messages)

        metrics = router.get_routing_metrics()
        assert metrics["total_routed"] == 1
        assert "by_tier" in metrics
        assert "by_complexity" in metrics

    def test_agent_config_handling(self):
        """Test agent config in routing decision."""
        router = ConversationLoopModelRouter()
        messages = [{"role": "user", "content": "Help"}]

        agent_config = {
            "model": "claude-sonnet-5",
            "provider": "anthropic",
            "enable_speculative": False,
            "enable_ensemble": True,
        }

        decision = router.route_request(messages, agent_config=agent_config)
        assert decision.should_ensemble is True

    def test_multiple_tools(self):
        """Test routing with multiple tools."""
        router = ConversationLoopModelRouter()
        messages = [{"role": "user", "content": "Help"}]

        tools = [
            {"name": f"tool_{i}", "description": f"Tool {i}"}
            for i in range(20)
        ]

        decision = router.route_request(messages, tools=tools)
        assert decision.complexity_score > 20

    def test_tool_tier_map(self):
        """Test model tier mapping."""
        router = ConversationLoopModelRouter()

        tier_map = router.model_tier_map
        assert ModelTier.FAST_CHEAP in tier_map
        assert ModelTier.BALANCED in tier_map
        assert ModelTier.CAPABLE in tier_map
        assert ModelTier.EXTENDED in tier_map

        for tier, models in tier_map.items():
            assert isinstance(models, list)
            assert len(models) > 0
            for model in models:
                assert isinstance(model, str)

    def test_reasoning_generation(self):
        """Test reasoning string generation."""
        router = ConversationLoopModelRouter()
        messages = [
            {
                "role": "user",
                "content": """
                def func():
                    pass
                How to optimize?
                """
            }
        ]

        decision = router.route_request(messages)
        assert len(decision.reasoning) > 0
        assert "Tier:" in decision.reasoning
        assert "Model:" in decision.reasoning


class TestSingletonRouter:
    """Test singleton router instance."""

    def test_get_model_router_singleton(self):
        """Test get_model_router returns singleton."""
        router1 = get_model_router()
        router2 = get_model_router()
        assert router1 is router2

    def test_route_request_function(self):
        """Test route_request convenience function."""
        messages = [{"role": "user", "content": "Read"}]

        decision = route_request(messages)

        assert isinstance(decision, RoutingDecision)
        assert decision.primary_model is not None
        assert decision.tier is not None


class TestRoutingIntegration:
    """Integration tests for routing."""

    def test_sequential_requests(self):
        """Test sequential request routing."""
        router = ConversationLoopModelRouter()

        # First request (simple)
        messages1 = [{"role": "user", "content": "Read"}]
        decision1 = router.route_request(messages1)

        # Second request (complex)
        messages2 = [{"role": "user", "content": "Design architecture"}]
        decision2 = router.route_request(messages2)

        # Third request (moderate)
        messages3 = [{"role": "user", "content": "Analyze data"}]
        decision3 = router.route_request(messages3)

        # All should be valid
        assert decision1.primary_model is not None
        assert decision2.primary_model is not None
        assert decision3.primary_model is not None

        # Complexity should be increasing
        assert decision1.complexity_score < decision2.complexity_score

    def test_model_diversity(self):
        """Test that different complexity levels use different models."""
        router = ConversationLoopModelRouter()

        simple_msg = [{"role": "user", "content": "Read"}]
        complex_msg = [{"role": "user", "content": "Design " * 50}]

        simple_decision = router.route_request(simple_msg)
        complex_decision = router.route_request(complex_msg)

        # Different tiers -> likely different models (or at least different tiers)
        assert simple_decision.tier != complex_decision.tier or simple_decision.complexity_score < complex_decision.complexity_score


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
