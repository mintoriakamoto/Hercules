"""DEPRECATED: Use agent.compression.conversation instead.

This module is maintained for backward compatibility.
All functionality has been moved to agent/compression/conversation.py.

The old import path is an alias of the new module, not a copy of its public
names: private helpers such as ``_CompressionLockLeaseRefresher`` stay
importable here, and ``patch("agent.conversation_compression.X")`` patches the
object the compression code actually uses.
"""

import sys

from agent.compression import conversation as _conversation

sys.modules[__name__] = _conversation
