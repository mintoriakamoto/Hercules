"""DEPRECATED: Use agent.compression.conversation instead.

This module is maintained for backward compatibility.
All functionality has been moved to agent/compression/conversation.py.

The entire compression subsystem has been consolidated into agent/compression/
while maintaining 100% backward compatibility through these re-exports.
No code changes are required in existing imports.
"""

# Re-export everything from the new location for backward compatibility
from agent.compression.conversation import *  # noqa: F401,F403

# Explicit re-exports of commonly-used names for IDE/type-checker support
from agent.compression.conversation import (
    COMPACTION_STATUS,
    COMPACTION_STATUS_MARKER,
    conversation_history_after_compression,
    check_compression_model_feasibility,
    replay_compression_warning,
)

__all__ = [
    "COMPACTION_STATUS",
    "COMPACTION_STATUS_MARKER",
    "conversation_history_after_compression",
    "check_compression_model_feasibility",
    "replay_compression_warning",
]
