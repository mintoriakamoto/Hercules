"""Consolidated compression package.

Consolidates trajectory compression, context compression, conversation handling,
and compression strategies into a single package while maintaining 100%
backward compatibility through re-exports in the original module locations.

Structure:
  - context.py: ContextCompressor and context window compression logic
  - conversation.py: Conversation-level compression orchestration
  - strategy.py: Unified compression strategy interface and implementations
  - (trajectory_compressor.py stays in root as a standalone script)

For backward compatibility, all exports are re-exported from original locations:
  - agent.context_compressor (re-exports from .context)
  - agent.conversation_compression (re-exports from .conversation)
  - agent.compression_strategy (re-exports from .strategy)
"""

# Re-export all public APIs for convenience when importing from the package
from .context import (
    ContextCompressor,
    HISTORICAL_TASK_HEADING,
    HISTORICAL_IN_PROGRESS_HEADING,
    HISTORICAL_PENDING_ASKS_HEADING,
    HISTORICAL_REMAINING_WORK_HEADING,
    SUMMARY_PREFIX,
    LEGACY_SUMMARY_PREFIX,
    estimate_messages_tokens_rough,
    MINIMUM_CONTEXT_LENGTH,
)

from .conversation import (
    COMPACTION_STATUS,
    COMPACTION_STATUS_MARKER,
    conversation_history_after_compression,
    check_compression_model_feasibility,
    replay_compression_warning,
)

from .strategy import (
    CompressionLevel,
    CompressionMetrics,
    CompressionStrategy,
    NoCompression,
    ConservativeCompression,
    BalancedCompression,
    AggressiveCompression,
    StrategyFactory,
    Compressor,
    get_default_compressor,
    set_default_compressor,
)

# Infinite memory system modules
from . import streaming, hierarchical, tool_outputs, infinite_memory

__all__ = [
    # From context
    "ContextCompressor",
    "HISTORICAL_TASK_HEADING",
    "HISTORICAL_IN_PROGRESS_HEADING",
    "HISTORICAL_PENDING_ASKS_HEADING",
    "HISTORICAL_REMAINING_WORK_HEADING",
    "SUMMARY_PREFIX",
    "LEGACY_SUMMARY_PREFIX",
    "estimate_messages_tokens_rough",
    "MINIMUM_CONTEXT_LENGTH",
    # From conversation
    "COMPACTION_STATUS",
    "COMPACTION_STATUS_MARKER",
    "conversation_history_after_compression",
    "check_compression_model_feasibility",
    "replay_compression_warning",
    # From strategy
    "CompressionLevel",
    "CompressionMetrics",
    "CompressionStrategy",
    "NoCompression",
    "ConservativeCompression",
    "BalancedCompression",
    "AggressiveCompression",
    "StrategyFactory",
    "Compressor",
    "get_default_compressor",
    "set_default_compressor",
    # Infinite memory system
    "streaming",
    "hierarchical",
    "tool_outputs",
    "infinite_memory",
]
