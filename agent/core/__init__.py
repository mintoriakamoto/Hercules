"""Core agent functionality - no external dependencies beyond stdlib + anthropic.

This package contains the fundamental agent runtime:
- Message handling
- Conversation loop coordination
- Basic execution infrastructure

Everything here must work without optional packages.
"""

from agent.execution.fast_inference import (
    InferenceCache,
    ContextPruner,
    FastInferenceEngine,
)
from agent.execution.tool_batching import (
    ParallelToolExecutor,
    ToolCall,
    ToolDependencyGraph,
)

__all__ = [
    "InferenceCache",
    "ContextPruner",
    "FastInferenceEngine",
    "ParallelToolExecutor",
    "ToolCall",
    "ToolDependencyGraph",
]
