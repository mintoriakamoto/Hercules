"""DEPRECATED: Use agent.compression.context instead.

This name is kept for backward compatibility. It is an alias of
``agent.compression.context`` itself (not a copy of its public names), so
private helpers stay importable and ``mock.patch("agent.context_compressor.X")``
patches the code that actually runs.
"""

import sys

from agent.compression import context as _context

sys.modules[__name__] = _context
