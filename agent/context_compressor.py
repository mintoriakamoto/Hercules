"""DEPRECATED: Use agent.compression.context instead.

This module is maintained for backward compatibility.
All functionality has been moved to agent/compression/context.py.

The entire compression subsystem has been consolidated into agent/compression/
while maintaining 100% backward compatibility through these re-exports.
No code changes are required in existing imports.
"""

# Re-export everything from the new location for backward compatibility
from agent.compression.context import *  # noqa: F401,F403

# Explicit re-exports of commonly-used names for IDE/type-checker support
from agent.compression.context import (
    ContextCompressor,
    HISTORICAL_TASK_HEADING,
    HISTORICAL_IN_PROGRESS_HEADING,
    HISTORICAL_PENDING_ASKS_HEADING,
    HISTORICAL_REMAINING_WORK_HEADING,
    SUMMARY_PREFIX,
    LEGACY_SUMMARY_PREFIX,
    estimate_messages_tokens_rough,
)

__all__ = [
    "ContextCompressor",
    "HISTORICAL_TASK_HEADING",
    "HISTORICAL_IN_PROGRESS_HEADING",
    "HISTORICAL_PENDING_ASKS_HEADING",
    "HISTORICAL_REMAINING_WORK_HEADING",
    "SUMMARY_PREFIX",
    "LEGACY_SUMMARY_PREFIX",
    "estimate_messages_tokens_rough",
]
