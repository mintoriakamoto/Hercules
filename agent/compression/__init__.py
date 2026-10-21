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

# Lazy imports to avoid hard dependency on optional packages (e.g., httpx)
# These are only loaded when actually used, not on package import
_context_exports = None
_conversation_exports = None
_strategy_exports = None


def __getattr__(name):
    """Lazy load compression modules on first access."""
    global _context_exports, _conversation_exports, _strategy_exports

    if name == "ContextCompressor":
        if _context_exports is None:
            from .context import ContextCompressor
        return ContextCompressor
    elif name == "HISTORICAL_TASK_HEADING":
        from .context import HISTORICAL_TASK_HEADING
        return HISTORICAL_TASK_HEADING
    elif name == "HISTORICAL_IN_PROGRESS_HEADING":
        from .context import HISTORICAL_IN_PROGRESS_HEADING
        return HISTORICAL_IN_PROGRESS_HEADING
    elif name == "HISTORICAL_PENDING_ASKS_HEADING":
        from .context import HISTORICAL_PENDING_ASKS_HEADING
        return HISTORICAL_PENDING_ASKS_HEADING
    elif name == "HISTORICAL_REMAINING_WORK_HEADING":
        from .context import HISTORICAL_REMAINING_WORK_HEADING
        return HISTORICAL_REMAINING_WORK_HEADING
    elif name == "SUMMARY_PREFIX":
        from .context import SUMMARY_PREFIX
        return SUMMARY_PREFIX
    elif name == "LEGACY_SUMMARY_PREFIX":
        from .context import LEGACY_SUMMARY_PREFIX
        return LEGACY_SUMMARY_PREFIX
    elif name == "estimate_messages_tokens_rough":
        from .context import estimate_messages_tokens_rough
        return estimate_messages_tokens_rough
    elif name == "MINIMUM_CONTEXT_LENGTH":
        from .context import MINIMUM_CONTEXT_LENGTH
        return MINIMUM_CONTEXT_LENGTH
    elif name == "COMPACTION_STATUS":
        from .conversation import COMPACTION_STATUS
        return COMPACTION_STATUS
    elif name == "COMPACTION_STATUS_MARKER":
        from .conversation import COMPACTION_STATUS_MARKER
        return COMPACTION_STATUS_MARKER
    elif name == "conversation_history_after_compression":
        from .conversation import conversation_history_after_compression
        return conversation_history_after_compression
    elif name == "check_compression_model_feasibility":
        from .conversation import check_compression_model_feasibility
        return check_compression_model_feasibility
    elif name == "replay_compression_warning":
        from .conversation import replay_compression_warning
        return replay_compression_warning
    elif name == "CompressionLevel":
        from .strategy import CompressionLevel
        return CompressionLevel
    elif name == "CompressionMetrics":
        from .strategy import CompressionMetrics
        return CompressionMetrics
    elif name == "CompressionStrategy":
        from .strategy import CompressionStrategy
        return CompressionStrategy
    elif name == "NoCompression":
        from .strategy import NoCompression
        return NoCompression
    elif name == "ConservativeCompression":
        from .strategy import ConservativeCompression
        return ConservativeCompression
    elif name == "BalancedCompression":
        from .strategy import BalancedCompression
        return BalancedCompression
    elif name == "AggressiveCompression":
        from .strategy import AggressiveCompression
        return AggressiveCompression
    elif name == "StrategyFactory":
        from .strategy import StrategyFactory
        return StrategyFactory
    elif name == "Compressor":
        from .strategy import Compressor
        return Compressor
    elif name == "get_default_compressor":
        from .strategy import get_default_compressor
        return get_default_compressor
    elif name == "set_default_compressor":
        from .strategy import set_default_compressor
        return set_default_compressor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Infinite memory system modules - these are lightweight and safe to import
try:
    from . import streaming, hierarchical, tool_outputs, infinite_memory
except ImportError:
    # If httpx isn't available, create placeholder modules
    class _PlaceholderModule:
        def __getattr__(self, name):
            raise ImportError("Optional dependencies not installed")
    streaming = _PlaceholderModule()
    hierarchical = _PlaceholderModule()
    tool_outputs = _PlaceholderModule()
    infinite_memory = _PlaceholderModule()

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
