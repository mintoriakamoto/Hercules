"""Knowledge management system for persistent learning across sessions.

This package provides persistent storage and retrieval of learnable facts
extracted during agent conversations. Facts are automatically extracted,
stored with confidence scores, and retrieved when relevant to current queries.

Key modules:
  - persistent_store: SQLite-backed knowledge storage with auto-extraction
  - retrieval: Semantic and keyword-based fact retrieval
  - pruning: Automatic cleanup of low-confidence or outdated facts
"""
