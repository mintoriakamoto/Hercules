"""Ensemble consensus mechanisms for high-stakes operations."""

from agent.ensemble.voting import (
    EnsembleVotingEngine,
    EnsembleVerdictResult,
    EnsembleStrategy,
    ModelVote,
    get_voting_engine,
)

__all__ = [
    "EnsembleVotingEngine",
    "EnsembleVerdictResult",
    "EnsembleStrategy",
    "ModelVote",
    "get_voting_engine",
]
