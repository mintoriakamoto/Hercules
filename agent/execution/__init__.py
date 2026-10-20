"""Execution strategies for model routing and fast inference."""

from agent.execution.speculative import (
    SpeculativeExecutionPipeline,
    SpeculativeResult,
    SpeculativeMetrics,
    get_speculative_pipeline,
)
from agent.execution.fast_inference import (
    FastInferenceEngine,
    InferenceCache,
    ContextPruner,
    ParallelInference,
    FastInferenceResult,
)
from agent.execution.tool_batching import (
    ParallelToolExecutor,
    ToolCall,
    ToolResult,
    ToolDependencyGraph,
    ToolResultCache,
)

__all__ = [
    # Speculative execution
    "SpeculativeExecutionPipeline",
    "SpeculativeResult",
    "SpeculativeMetrics",
    "get_speculative_pipeline",
    # Fast inference
    "FastInferenceEngine",
    "InferenceCache",
    "ContextPruner",
    "ParallelInference",
    "FastInferenceResult",
    # Tool batching
    "ParallelToolExecutor",
    "ToolCall",
    "ToolResult",
    "ToolDependencyGraph",
    "ToolResultCache",
]
