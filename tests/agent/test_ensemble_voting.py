"""Tests for ensemble voting mechanism."""

import asyncio
import pytest

from agent.ensemble.voting import (
    EnsembleVotingEngine,
    EnsembleVerdictResult,
    EnsembleStrategy,
    ModelVote,
    get_voting_engine,
)


class TestEnsembleVotingEngine:
    """Test ensemble voting engine."""

    def test_engine_initialization(self):
        """Test that voting engine initializes properly."""
        engine = EnsembleVotingEngine()
        assert engine is not None
        assert engine.default_strategy == EnsembleStrategy.MAJORITY
        assert len(engine.voting_history) == 0

    @pytest.mark.asyncio
    async def test_majority_voting(self):
        """Test majority voting strategy."""

        async def model1():
            return {"response": "A"}, 0.8, 100.0

        async def model2():
            return {"response": "A"}, 0.75, 120.0

        async def model3():
            return {"response": "B"}, 0.7, 110.0

        engine = EnsembleVotingEngine()
        model_calls = [
            ("model1", model1),
            ("model2", model2),
            ("model3", model3),
        ]

        verdict = await engine.ensemble_vote(
            model_calls,
            task_type="general",
            strategy=EnsembleStrategy.MAJORITY,
            timeout_ms=5000
        )

        assert verdict.winning_model in ["model1", "model2"]
        assert verdict.strategy == EnsembleStrategy.MAJORITY
        assert verdict.agreement_level > 0.0
        assert len(verdict.all_votes) == 3

    @pytest.mark.asyncio
    async def test_unanimous_voting(self):
        """Test unanimous voting strategy."""

        async def model1():
            return {"response": "safe"}, 0.9, 100.0

        async def model2():
            return {"response": "safe"}, 0.85, 110.0

        async def model3():
            return {"response": "safe"}, 0.8, 120.0

        engine = EnsembleVotingEngine()
        model_calls = [
            ("model1", model1),
            ("model2", model2),
            ("model3", model3),
        ]

        verdict = await engine.ensemble_vote(
            model_calls,
            task_type="security",
            strategy=EnsembleStrategy.UNANIMOUS
        )

        assert verdict.agreement_level == 1.0  # Perfect agreement
        assert verdict.strategy == EnsembleStrategy.UNANIMOUS

    @pytest.mark.asyncio
    async def test_best_confidence_voting(self):
        """Test best confidence voting strategy."""

        async def model1():
            return {"response": "A"}, 0.5, 100.0

        async def model2():
            return {"response": "B"}, 0.95, 110.0

        async def model3():
            return {"response": "A"}, 0.6, 120.0

        engine = EnsembleVotingEngine()
        model_calls = [
            ("model1", model1),
            ("model2", model2),
            ("model3", model3),
        ]

        verdict = await engine.ensemble_vote(
            model_calls,
            task_type="code",
            strategy=EnsembleStrategy.BEST_CONFIDENCE
        )

        assert verdict.winning_model == "model2"
        assert verdict.confidence == pytest.approx(0.95)

    @pytest.mark.asyncio
    async def test_weighted_voting(self):
        """Test weighted voting strategy."""

        async def model1():
            return {"response": "A"}, 0.9, 100.0

        async def model2():
            return {"response": "B"}, 0.3, 110.0

        async def model3():
            return {"response": "A"}, 0.8, 120.0

        engine = EnsembleVotingEngine()
        model_calls = [
            ("model1", model1),
            ("model2", model2),
            ("model3", model3),
        ]

        verdict = await engine.ensemble_vote(
            model_calls,
            task_type="architecture",
            strategy=EnsembleStrategy.WEIGHTED
        )

        # Response "A" should win due to higher weights
        assert verdict.winning_response == {"response": "A"}

    @pytest.mark.asyncio
    async def test_strategy_selection(self):
        """Test automatic strategy selection by task type."""
        engine = EnsembleVotingEngine()

        assert engine._select_strategy("security") == EnsembleStrategy.UNANIMOUS
        assert engine._select_strategy("code") == EnsembleStrategy.BEST_CONFIDENCE
        assert engine._select_strategy("architecture") == EnsembleStrategy.WEIGHTED
        assert engine._select_strategy("general") == EnsembleStrategy.MAJORITY

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test timeout handling in voting."""

        async def slow_model():
            await asyncio.sleep(10)
            return {"response": "slow"}, 0.8, 10000.0

        async def fast_model():
            return {"response": "fast"}, 0.7, 100.0

        engine = EnsembleVotingEngine()
        model_calls = [
            ("slow", slow_model),
            ("fast", fast_model),
        ]

        verdict = await engine.ensemble_vote(
            model_calls,
            timeout_ms=500
        )

        # Should still get a verdict with available models
        assert verdict.winning_model is not None
        assert verdict.execution_time_ms <= 2000  # Some overhead ok

    @pytest.mark.asyncio
    async def test_failed_models_handling(self):
        """Test handling of failed models."""

        async def failed_model():
            raise Exception("Model failed")

        async def working_model():
            return {"response": "success"}, 0.8, 100.0

        engine = EnsembleVotingEngine()
        model_calls = [
            ("failed", failed_model),
            ("working", working_model),
        ]

        verdict = await engine.ensemble_vote(
            model_calls
        )

        # Should use working model
        assert verdict.winning_model == "working"
        assert verdict.agreement_level > 0.0

    @pytest.mark.asyncio
    async def test_all_models_failed(self):
        """Test handling when all models fail."""

        async def failed1():
            raise Exception("Failed 1")

        async def failed2():
            raise Exception("Failed 2")

        engine = EnsembleVotingEngine()
        model_calls = [
            ("model1", failed1),
            ("model2", failed2),
        ]

        verdict = await engine.ensemble_vote(
            model_calls
        )

        assert verdict.winning_response is None
        assert verdict.agreement_level == 0.0

    def test_voting_history(self):
        """Test voting history tracking."""
        engine = EnsembleVotingEngine()

        # Manually add to history
        engine.voting_history.append({
            "timestamp": 0,
            "task_type": "code",
            "strategy": "best_confidence",
            "num_models": 3,
            "agreement_level": 0.8,
            "execution_time_ms": 250
        })

        history = engine.get_voting_history(limit=10)
        assert len(history) == 1
        assert history[0]["task_type"] == "code"

    def test_singleton_instance(self):
        """Test that get_voting_engine returns singleton."""
        engine1 = get_voting_engine()
        engine2 = get_voting_engine()
        assert engine1 is engine2


class TestModelVote:
    """Test model vote representation."""

    def test_model_vote_creation(self):
        """Test model vote creation."""
        vote = ModelVote(
            model_name="test_model",
            response={"answer": "yes"},
            confidence=0.95,
            execution_time_ms=150,
            succeeded=True
        )

        assert vote.model_name == "test_model"
        assert vote.confidence == 0.95
        assert vote.succeeded is True


class TestEnsembleVerdictResult:
    """Test ensemble verdict result."""

    def test_verdict_result_creation(self):
        """Test verdict result creation."""
        result = EnsembleVerdictResult(
            winning_response={"answer": "yes"},
            winning_model="model1",
            strategy=EnsembleStrategy.MAJORITY,
            agreement_level=0.9,
            execution_time_ms=300,
            reasoning="Model 1 won with majority vote"
        )

        assert result.winning_model == "model1"
        assert result.agreement_level == 0.9
        assert result.strategy == EnsembleStrategy.MAJORITY


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
