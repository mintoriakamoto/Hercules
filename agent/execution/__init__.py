"""Execution strategies for model routing."""

from agent.execution.speculative import (
    SpeculativeExecutionPipeline,
    SpeculativeResult,
    SpeculativeMetrics,
    get_speculative_pipeline,
)

__all__ = [
    "SpeculativeExecutionPipeline",
    "SpeculativeResult",
    "SpeculativeMetrics",
    "get_speculative_pipeline",
]
