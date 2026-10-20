"""Ensemble consensus for high-stakes operations.

For critical operations, run multiple models in parallel and vote on result:

Strategies by task type:
- CODE_GENERATION: Highest test pass rate wins
- SECURITY_DECISIONS: Unanimous approval required (conservative)
- ARCHITECTURE: Majority vote with confidence weighting
- GENERAL: Confidence-weighted voting

Timeout: 5s max, use majority if slowest times out.
"""

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class EnsembleStrategy(str, Enum):
    """Voting strategies for ensemble decisions."""

    MAJORITY = "majority"  # Majority vote
    UNANIMOUS = "unanimous"  # All must agree
    WEIGHTED = "weighted"  # Confidence-weighted voting
    BEST_CONFIDENCE = "best_confidence"  # Highest confidence wins


@dataclass
class ModelVote:
    """Vote from a single model."""

    model_name: str
    response: Any
    confidence: float  # 0.0-1.0
    execution_time_ms: float
    succeeded: bool


@dataclass
class EnsembleVerdictResult:
    """Result of ensemble voting."""

    winning_response: Any
    winning_model: str
    strategy: EnsembleStrategy
    agreement_level: float  # 0.0-1.0 (proportion of models that agreed)
    execution_time_ms: float
    all_votes: List[ModelVote] = field(default_factory=list)
    reasoning: str = ""
    confidence: float = 0.0


class EnsembleVotingEngine:
    """Manages ensemble voting for consensus decisions."""

    def __init__(self, default_strategy: EnsembleStrategy = EnsembleStrategy.MAJORITY):
        """Initialize voting engine."""
        self.default_strategy = default_strategy
        self.voting_history: List[Dict[str, Any]] = []

    async def ensemble_vote(
        self,
        model_calls: List[Tuple[str, Any]],  # List of (model_name, async_call)
        task_type: str = "general",
        strategy: Optional[EnsembleStrategy] = None,
        timeout_ms: int = 5000
    ) -> EnsembleVerdictResult:
        """
        Run multiple models and vote on result.

        Args:
            model_calls: List of (model_name, async_callable) tuples
            task_type: Type of task (code, security, architecture, general)
            strategy: Voting strategy (uses default if not specified)
            timeout_ms: Maximum time to wait for all models

        Returns:
            EnsembleVerdictResult with winning response and confidence
        """
        if not model_calls:
            raise ValueError("No model calls provided for ensemble voting")

        if strategy is None:
            strategy = self._select_strategy(task_type)

        start_time = time.time()
        votes: List[ModelVote] = []

        # Create tasks for all models
        tasks = [
            self._call_model_with_timeout(name, call, timeout_ms // len(model_calls))
            for name, call in model_calls
        ]

        # Gather results
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
        except asyncio.TimeoutError:
            logger.warning("Ensemble voting timed out after %dms", timeout_ms)
            results = [None] * len(tasks)

        # Process results into votes
        for (model_name, _), result in zip(model_calls, results):
            if isinstance(result, Exception):
                logger.debug("Model %s failed: %s", model_name, str(result)[:100])
                votes.append(ModelVote(
                    model_name=model_name,
                    response=None,
                    confidence=0.0,
                    execution_time_ms=-1,
                    succeeded=False
                ))
            elif result is not None:
                response, confidence, exec_time = result
                votes.append(ModelVote(
                    model_name=model_name,
                    response=response,
                    confidence=confidence,
                    execution_time_ms=exec_time,
                    succeeded=True
                ))

        # Select winner based on strategy
        verdict = self._apply_voting_strategy(
            votes, strategy, task_type
        )

        verdict.all_votes = votes
        verdict.execution_time_ms = (time.time() - start_time) * 1000

        # Record in history
        self.voting_history.append({
            "timestamp": time.time(),
            "task_type": task_type,
            "strategy": strategy.value,
            "num_models": len(model_calls),
            "agreement_level": verdict.agreement_level,
            "execution_time_ms": verdict.execution_time_ms
        })

        logger.info(
            "Ensemble voting complete: task=%s, strategy=%s, agreement=%.1f%%, "
            "winner=%s, time=%.0fms",
            task_type, strategy.value, verdict.agreement_level * 100,
            verdict.winning_model, verdict.execution_time_ms
        )

        return verdict

    def _select_strategy(self, task_type: str) -> EnsembleStrategy:
        """Select voting strategy based on task type."""
        if task_type == "security":
            return EnsembleStrategy.UNANIMOUS
        elif task_type == "code":
            return EnsembleStrategy.BEST_CONFIDENCE
        elif task_type == "architecture":
            return EnsembleStrategy.WEIGHTED
        else:
            return EnsembleStrategy.MAJORITY

    async def _call_model_with_timeout(
        self,
        model_name: str,
        call,
        timeout_ms: int
    ) -> Tuple[Any, float, float]:
        """Call model with timeout and return response, confidence, execution time."""
        start_time = time.time()
        try:
            result = await asyncio.wait_for(
                call,
                timeout=timeout_ms / 1000.0
            )
            exec_time = (time.time() - start_time) * 1000

            # Extract response and confidence
            if isinstance(result, dict):
                response = result.get("response") or result
                confidence = result.get("confidence", 0.7)
            else:
                response = result
                confidence = 0.7

            return response, confidence, exec_time
        except asyncio.TimeoutError:
            exec_time = (time.time() - start_time) * 1000
            logger.warning("Model %s timed out after %.0fms", model_name, exec_time)
            return None, 0.0, exec_time

    def _apply_voting_strategy(
        self,
        votes: List[ModelVote],
        strategy: EnsembleStrategy,
        task_type: str
    ) -> EnsembleVerdictResult:
        """Apply voting strategy to determine winner."""
        successful_votes = [v for v in votes if v.succeeded]

        if not successful_votes:
            # All models failed - return empty result
            return EnsembleVerdictResult(
                winning_response=None,
                winning_model="none",
                strategy=strategy,
                agreement_level=0.0,
                execution_time_ms=0.0,
                reasoning="All models failed"
            )

        if strategy == EnsembleStrategy.UNANIMOUS:
            return self._vote_unanimous(successful_votes, task_type)
        elif strategy == EnsembleStrategy.BEST_CONFIDENCE:
            return self._vote_best_confidence(successful_votes, task_type)
        elif strategy == EnsembleStrategy.WEIGHTED:
            return self._vote_weighted(successful_votes, task_type)
        else:  # MAJORITY
            return self._vote_majority(successful_votes, task_type)

    def _vote_unanimous(
        self,
        votes: List[ModelVote],
        task_type: str
    ) -> EnsembleVerdictResult:
        """Unanimous voting - all must agree."""
        if not votes:
            return EnsembleVerdictResult(
                winning_response=None,
                winning_model="none",
                strategy=EnsembleStrategy.UNANIMOUS,
                agreement_level=0.0,
                execution_time_ms=0.0,
                reasoning="No successful votes"
            )

        # For security, check if all responses are "safe" or equivalent
        response_hashes = [
            hashlib.md5(str(v.response).encode()).hexdigest()[:8]
            for v in votes
        ]

        unique_responses = len(set(response_hashes))
        agreement_level = (len(votes) - unique_responses + 1) / len(votes)

        if unique_responses == 1:
            # Perfect agreement
            winner = votes[0]
            confidence = min(v.confidence for v in votes)
            reasoning = "Unanimous agreement among all models"
        elif agreement_level >= 0.8:
            # Strong agreement (80%+)
            winner = max(votes, key=lambda v: v.confidence)
            confidence = winner.confidence
            reasoning = f"Strong agreement ({int(agreement_level * 100)}%)"
        else:
            # Weak agreement - use highest confidence
            winner = max(votes, key=lambda v: v.confidence)
            confidence = winner.confidence
            reasoning = f"Low agreement ({int(agreement_level * 100)}%); using highest confidence"

        return EnsembleVerdictResult(
            winning_response=winner.response,
            winning_model=winner.model_name,
            strategy=EnsembleStrategy.UNANIMOUS,
            agreement_level=agreement_level,
            execution_time_ms=max(v.execution_time_ms for v in votes),
            reasoning=reasoning,
            confidence=confidence
        )

    def _vote_best_confidence(
        self,
        votes: List[ModelVote],
        task_type: str
    ) -> EnsembleVerdictResult:
        """Best confidence voting - highest confidence wins."""
        winner = max(votes, key=lambda v: v.confidence)

        # Calculate agreement as proportion voting for top response
        response_hash = hashlib.md5(str(winner.response).encode()).hexdigest()[:8]
        agreement_votes = sum(
            1 for v in votes
            if hashlib.md5(str(v.response).encode()).hexdigest()[:8] == response_hash
        )
        agreement_level = agreement_votes / len(votes)

        return EnsembleVerdictResult(
            winning_response=winner.response,
            winning_model=winner.model_name,
            strategy=EnsembleStrategy.BEST_CONFIDENCE,
            agreement_level=agreement_level,
            execution_time_ms=winner.execution_time_ms,
            reasoning=f"Highest confidence ({winner.confidence:.1%}) from {winner.model_name}",
            confidence=winner.confidence
        )

    def _vote_weighted(
        self,
        votes: List[ModelVote],
        task_type: str
    ) -> EnsembleVerdictResult:
        """Confidence-weighted voting."""
        # Weight votes by confidence
        total_weight = sum(v.confidence for v in votes)
        if total_weight == 0:
            # Fallback to uniform weighting
            weights = {i: 1.0 / len(votes) for i in range(len(votes))}
        else:
            weights = {i: v.confidence / total_weight for i, v in enumerate(votes)}

        # Find response with highest weighted agreement
        response_scores: Dict[str, float] = {}
        response_to_vote: Dict[str, int] = {}

        for i, vote in enumerate(votes):
            response_hash = hashlib.md5(str(vote.response).encode()).hexdigest()[:8]
            response_scores[response_hash] = response_scores.get(response_hash, 0.0) + weights[i]
            if response_hash not in response_to_vote:
                response_to_vote[response_hash] = i

        # Winner is response with highest weighted score
        best_hash = max(response_scores, key=response_scores.get)
        best_vote_idx = response_to_vote[best_hash]
        winner = votes[best_vote_idx]

        agreement_level = response_scores[best_hash]

        return EnsembleVerdictResult(
            winning_response=winner.response,
            winning_model=winner.model_name,
            strategy=EnsembleStrategy.WEIGHTED,
            agreement_level=agreement_level,
            execution_time_ms=max(v.execution_time_ms for v in votes),
            reasoning=f"Weighted voting: {winner.model_name} won with {agreement_level:.1%} support",
            confidence=winner.confidence
        )

    def _vote_majority(
        self,
        votes: List[ModelVote],
        task_type: str
    ) -> EnsembleVerdictResult:
        """Majority voting - most common response wins."""
        # Group votes by response hash
        response_groups: Dict[str, List[int]] = {}
        for i, vote in enumerate(votes):
            response_hash = hashlib.md5(str(vote.response).encode()).hexdigest()[:8]
            if response_hash not in response_groups:
                response_groups[response_hash] = []
            response_groups[response_hash].append(i)

        # Find response with most votes
        best_hash = max(response_groups, key=lambda h: len(response_groups[h]))
        best_vote_indices = response_groups[best_hash]
        winner = votes[best_vote_indices[0]]

        agreement_level = len(best_vote_indices) / len(votes)

        return EnsembleVerdictResult(
            winning_response=winner.response,
            winning_model=winner.model_name,
            strategy=EnsembleStrategy.MAJORITY,
            agreement_level=agreement_level,
            execution_time_ms=max(v.execution_time_ms for v in votes),
            reasoning=f"Majority vote: {winner.model_name} won with {len(best_vote_indices)}/{len(votes)} votes",
            confidence=sum(votes[i].confidence for i in best_vote_indices) / len(best_vote_indices)
        )

    def get_voting_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent voting history."""
        return self.voting_history[-limit:]


# Singleton instance
_engine: Optional[EnsembleVotingEngine] = None


def get_voting_engine() -> EnsembleVotingEngine:
    """Get or create the ensemble voting engine."""
    global _engine
    if _engine is None:
        _engine = EnsembleVotingEngine(default_strategy=EnsembleStrategy.MAJORITY)
    return _engine
