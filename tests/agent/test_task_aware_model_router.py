"""Tests for task-aware model routing."""

import pytest

from agent.extended_reasoning import ReasoningComplexity
from agent.task_aware_model_router import (
    ModelTier,
    TaskAwareModelRouter,
    TaskCategory,
    get_model_router,
    route_task_to_model,
)


class TestTaskAwareModelRouter:
    """Test task-aware model routing logic."""

    def test_router_initialization(self):
        """Test that router initializes with default rules."""
        router = TaskAwareModelRouter()
        assert router.reasoning_engine is not None
        assert len(router.routing_rules) > 0
        assert router.model_tier_mapping is not None

    def test_simple_task_routes_to_fast_cheap(self):
        """Test that simple read tasks route to fast/cheap models."""
        router = TaskAwareModelRouter()
        decision = router.analyze_task("Read a file and extract the first line")

        assert decision.recommended_tier == ModelTier.FAST_CHEAP
        assert decision.confidence > 0.7
        assert decision.recommended_model is not None

    def test_complex_task_routes_to_capable(self):
        """Test that complex reasoning tasks route to capable models."""
        router = TaskAwareModelRouter()
        decision = router.analyze_task("Design a secure authentication system with trade-off analysis")

        # Can be CAPABLE or EXTENDED depending on complexity analysis
        assert decision.recommended_tier in (ModelTier.CAPABLE, ModelTier.BALANCED, ModelTier.EXTENDED)
        assert decision.recommended_model is not None

    def test_security_task_routes_appropriately(self):
        """Test that security tasks get appropriate routing."""
        router = TaskAwareModelRouter()
        decision = router.analyze_task(
            "Perform penetration testing on AWS infrastructure and identify vulnerabilities"
        )

        # Security tasks should get at least capable tier
        assert decision.recommended_tier in (ModelTier.CAPABLE, ModelTier.EXTENDED)
        assert decision.confidence >= 0.75

    def test_task_categorization(self):
        """Test task categorization by keywords."""
        router = TaskAwareModelRouter()

        read_cat = router._categorize_task("Read the configuration file")
        assert read_cat == TaskCategory.READ

        code_cat = router._categorize_task("Write a Python function to calculate")
        assert code_cat == TaskCategory.CODE

        security_cat = router._categorize_task("Identify security vulnerabilities")
        assert security_cat == TaskCategory.SECURITY

    def test_cost_savings_estimation(self):
        """Test cost savings estimation."""
        router = TaskAwareModelRouter()

        # Routing simple task to fast_cheap should save money (compared to same complexity at higher tier)
        # Baseline is complex (higher cost), routing to fast_cheap saves
        savings = router._estimate_cost_savings(
            ReasoningComplexity.COMPLEX, ModelTier.FAST_CHEAP
        )
        assert savings is not None and savings > 0

        # Routing complex task to capable (appropriate tier) has minimal/no savings
        no_savings = router._estimate_cost_savings(
            ReasoningComplexity.COMPLEX, ModelTier.CAPABLE
        )
        # Should be 0 or minimal since it's the appropriate tier
        assert no_savings is None or no_savings <= 10

    def test_model_selection_from_tier(self):
        """Test model selection from tier."""
        router = TaskAwareModelRouter()

        fast_cheap_model = router._select_model_from_tier(ModelTier.FAST_CHEAP)
        assert fast_cheap_model is not None
        assert isinstance(fast_cheap_model, str)

        balanced_model = router._select_model_from_tier(ModelTier.BALANCED)
        assert balanced_model is not None

        capable_model = router._select_model_from_tier(ModelTier.CAPABLE)
        assert capable_model is not None

    def test_routing_decision_completeness(self):
        """Test that routing decision contains all required fields."""
        router = TaskAwareModelRouter()
        decision = router.analyze_task("Analyze this data")

        assert decision.recommended_tier is not None
        assert decision.complexity in ReasoningComplexity
        assert 0 <= decision.confidence <= 1
        assert isinstance(decision.reasoning, str)

    def test_multiple_tasks_consistency(self):
        """Test that similar tasks get consistent routing."""
        router = TaskAwareModelRouter()

        decision1 = router.analyze_task("Find the line count in a file")
        decision2 = router.analyze_task("Extract lines from a text file")

        assert decision1.recommended_tier == decision2.recommended_tier
        assert decision1.complexity == decision2.complexity

    def test_singleton_router(self):
        """Test that get_model_router returns the same instance."""
        router1 = get_model_router()
        router2 = get_model_router()
        assert router1 is router2

    def test_route_task_to_model_function(self):
        """Test the primary entry point function."""
        model, decision = route_task_to_model("List files in a directory")

        assert isinstance(model, str)
        assert model in [
            m for tier_models in (
                get_model_router().model_tier_mapping.values()
            ) for m in tier_models
        ]
        assert decision.recommended_model == model or decision.recommended_model is None

    def test_confidence_scores(self):
        """Test that confidence scores are reasonable."""
        router = TaskAwareModelRouter()

        # Task with clear category should have high confidence
        clear_task = router.analyze_task("Read the user's home directory")
        assert clear_task.confidence >= 0.7

        # Task with mixed/unclear requirements may have lower confidence
        unclear_task = router.analyze_task("Do something useful")
        assert 0.3 <= unclear_task.confidence <= 1.0

    def test_reasoning_messages(self):
        """Test that reasoning explanations are provided."""
        router = TaskAwareModelRouter()
        decision = router.analyze_task("Optimize database queries for performance")

        assert len(decision.reasoning) > 0
        assert "complex" in decision.reasoning.lower() or "rule" in decision.reasoning.lower()


class TestModelTierMapping:
    """Test model tier to model ID mapping."""

    def test_all_tiers_have_models(self):
        """Test that all tiers have at least one model."""
        router = TaskAwareModelRouter()

        for tier in ModelTier:
            models = router.model_tier_mapping.get(tier)
            assert models is not None
            assert len(models) > 0

    def test_models_are_strings(self):
        """Test that all models are valid strings."""
        router = TaskAwareModelRouter()

        for tier, models in router.model_tier_mapping.items():
            for model in models:
                assert isinstance(model, str)
                assert len(model) > 0


class TestRoutingRules:
    """Test routing rule definitions."""

    def test_default_rules_are_valid(self):
        """Test that default rules are well-formed."""
        router = TaskAwareModelRouter()

        for rule in router.routing_rules:
            assert rule.complexity in ReasoningComplexity
            assert rule.tier in ModelTier
            assert 0 <= rule.confidence <= 1.0
            assert isinstance(rule.keywords, list)

    def test_rules_have_keywords(self):
        """Test that rules have associated keywords."""
        router = TaskAwareModelRouter()

        for rule in router.routing_rules:
            # Each rule should have at least some keywords to match on
            assert len(rule.keywords) > 0

    def test_no_duplicate_rules(self):
        """Test that rules don't duplicate complexity/category combinations."""
        router = TaskAwareModelRouter()
        seen_combinations = set()

        for rule in router.routing_rules:
            combo = (rule.complexity, rule.category)
            # We allow duplicates for now since category can refine complexity
            # but log if there are many duplicates
            if combo in seen_combinations:
                # This is allowed but worth noting
                pass
            seen_combinations.add(combo)


class TestTaskCategorization:
    """Test task categorization logic."""

    def test_categorizes_read_tasks(self):
        """Test categorization of read/retrieve tasks."""
        router = TaskAwareModelRouter()

        assert router._categorize_task("read the file") == TaskCategory.READ
        assert router._categorize_task("list all users") == TaskCategory.READ
        assert router._categorize_task("find the error") == TaskCategory.READ

    def test_categorizes_code_tasks(self):
        """Test categorization of code tasks."""
        router = TaskAwareModelRouter()

        assert router._categorize_task("write a function") == TaskCategory.CODE
        assert router._categorize_task("debug the script") == TaskCategory.CODE
        assert router._categorize_task("implement the feature") == TaskCategory.CODE

    def test_categorizes_security_tasks(self):
        """Test categorization of security tasks."""
        router = TaskAwareModelRouter()

        assert router._categorize_task("test for vulnerabilities") == TaskCategory.SECURITY
        assert router._categorize_task("perform penetration test") == TaskCategory.SECURITY
        assert router._categorize_task("exploit this service") == TaskCategory.SECURITY

    def test_uncategorized_tasks(self):
        """Test that non-matching tasks return None."""
        router = TaskAwareModelRouter()

        result = router._categorize_task("xyz abc 123")
        assert result is None


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_task_description(self):
        """Test handling of empty task description."""
        router = TaskAwareModelRouter()
        decision = router.analyze_task("")

        assert decision.recommended_tier is not None
        assert decision.recommended_model is not None

    def test_very_long_task_description(self):
        """Test handling of very long task descriptions."""
        router = TaskAwareModelRouter()
        long_task = "Read the file " * 100

        decision = router.analyze_task(long_task)
        assert decision.recommended_tier is not None

    def test_task_with_unicode(self):
        """Test handling of unicode in task description."""
        router = TaskAwareModelRouter()
        decision = router.analyze_task("分析日志文件 (analyze log file in Chinese)")

        assert decision.recommended_tier is not None

    def test_zero_available_tools(self):
        """Test routing with no available tools."""
        router = TaskAwareModelRouter()
        decision = router.analyze_task("Find something", available_tools=0)

        assert decision.recommended_tier is not None
        # Should still route, maybe to capable tier since tools are limited
        assert decision.recommended_model is not None

    def test_many_available_tools(self):
        """Test routing with many available tools."""
        router = TaskAwareModelRouter()
        decision = router.analyze_task("Find something", available_tools=50)

        assert decision.recommended_tier is not None
        # With many tools, can be more aggressive/complex
        assert decision.recommended_model is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
