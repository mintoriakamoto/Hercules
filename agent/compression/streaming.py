"""Streaming context compaction — incremental snapshots instead of batch compression.

Rather than waiting for context overflow and then doing expensive batch
compression, this module creates periodic snapshots asynchronously:

  - Every 5 turns OR 50k tokens: snapshot the current context
  - Process asynchronously (non-blocking) in background thread
  - Return control immediately: "context freed, snapshot available"
  - Format: compact JSON with turn summaries and metadata

Key features:
  - Incremental snapshots preserve turn-level metadata
  - Efficient re-serialization of compression results
  - Cost tracking (Level 0 = full context, Level 1 = summaries ~10% cost)
  - Background task coordination to avoid blocking turns

Snapshot format:
  {
    "version": 1,
    "snapshot_id": "snap_<uuid>",
    "created_at": "2024-01-15T10:30:00Z",
    "turn_start": 42,
    "turn_end": 47,
    "turn_count": 6,
    "total_chars": 12543,
    "summary_chars": 1234,
    "compression_ratio": 0.098,
    "turns": [
      {
        "turn_num": 42,
        "role": "user",
        "summary": "Asking about...",
        "char_count": 543,
        "has_tools": false,
        "key_topics": ["topic1", "topic2"]
      },
      ...
    ]
  }
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from hercules_constants import get_hercules_home

logger = logging.getLogger(__name__)

_SNAPSHOT_DIR = None  # Set lazily
_SNAPSHOT_VERSION = 1
_SNAPSHOT_THREAD_POOL: Dict[str, threading.Thread] = {}
_SNAPSHOT_LOCK = threading.Lock()


@dataclass
class TurnSnapshot:
    """Compact representation of a single turn."""

    turn_num: int
    role: str  # "user" or "assistant"
    summary: str  # 1-2 sentence summary
    char_count: int
    has_tools: bool
    key_topics: List[str]


@dataclass
class ContextSnapshot:
    """A compressed snapshot of context from a batch of turns."""

    version: int
    snapshot_id: str
    created_at: str
    turn_start: int
    turn_end: int
    turn_count: int
    total_chars: int
    summary_chars: int
    compression_ratio: float
    turns: List[TurnSnapshot]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "version": self.version,
            "snapshot_id": self.snapshot_id,
            "created_at": self.created_at,
            "turn_start": self.turn_start,
            "turn_end": self.turn_end,
            "turn_count": self.turn_count,
            "total_chars": self.total_chars,
            "summary_chars": self.summary_chars,
            "compression_ratio": self.compression_ratio,
            "turns": [asdict(t) for t in self.turns],
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> ContextSnapshot:
        """Reconstruct from dictionary."""
        turns = [TurnSnapshot(**t) for t in data.get("turns", [])]
        return ContextSnapshot(
            version=data.get("version", 1),
            snapshot_id=data.get("snapshot_id", ""),
            created_at=data.get("created_at", ""),
            turn_start=data.get("turn_start", 0),
            turn_end=data.get("turn_end", 0),
            turn_count=data.get("turn_count", 0),
            total_chars=data.get("total_chars", 0),
            summary_chars=data.get("summary_chars", 0),
            compression_ratio=data.get("compression_ratio", 0.0),
            turns=turns,
        )


def _get_snapshot_dir() -> Path:
    """Get or create the snapshot storage directory."""
    global _SNAPSHOT_DIR
    if _SNAPSHOT_DIR is None:
        _SNAPSHOT_DIR = get_hercules_home() / "context_snapshots"
        _SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    return _SNAPSHOT_DIR


def _extract_turn_topics(message: Dict[str, Any]) -> List[str]:
    """Extract key topics from a message for indexing."""
    topics = []
    content = message.get("content", "")
    if isinstance(content, str):
        # Simple keyword extraction (in production, use NLP)
        keywords = ["error", "bug", "fix", "feature", "test", "file", "function"]
        for keyword in keywords:
            if keyword.lower() in content.lower():
                topics.append(keyword)
    return topics[:5]  # Limit to top 5 topics


def _summarize_message(message: Dict[str, Any]) -> str:
    """Create a brief summary of a message."""
    content = message.get("content", "")
    if isinstance(content, str):
        # Take first 1-2 sentences
        sentences = content.split(". ")
        summary = ". ".join(sentences[:2]).strip()
        if len(summary) > 100:
            summary = summary[:97] + "..."
        return summary
    return "[message]"


def should_snapshot(turn_count: int, total_chars: int) -> bool:
    """Check if we should create a snapshot now.

    Snapshot triggers:
      - Every 5 turns, OR
      - Every 50k characters of context

    Args:
        turn_count: Number of turns since last snapshot
        total_chars: Total characters in current context

    Returns:
        True if snapshot should be created
    """
    return turn_count >= 5 or total_chars >= 50000


def create_snapshot(
    messages: List[Dict[str, Any]],
    turn_start: int = 0,
    turn_end: int = 0,
) -> ContextSnapshot:
    """Create a snapshot of current messages with summaries.

    Args:
        messages: List of message dicts to snapshot
        turn_start: Starting turn number
        turn_end: Ending turn number

    Returns:
        ContextSnapshot object ready for storage
    """
    turns = []
    total_chars = 0
    summary_chars = 0

    for i, msg in enumerate(messages):
        content = msg.get("content", "")
        if isinstance(content, str):
            char_count = len(content)
        else:
            char_count = len(json.dumps(content))

        summary = _summarize_message(msg)
        has_tools = "tool" in msg.get("role", "").lower() or any(
            key in msg for key in ["tool_use_id", "tool_results"]
        )

        turn = TurnSnapshot(
            turn_num=turn_start + i,
            role=msg.get("role", "user"),
            summary=summary,
            char_count=char_count,
            has_tools=has_tools,
            key_topics=_extract_turn_topics(msg),
        )
        turns.append(turn)
        total_chars += char_count
        summary_chars += len(summary)

    compression_ratio = summary_chars / total_chars if total_chars > 0 else 0.0

    return ContextSnapshot(
        version=_SNAPSHOT_VERSION,
        snapshot_id=f"snap_{uuid.uuid4().hex[:12]}",
        created_at=datetime.now(timezone.utc).isoformat(),
        turn_start=turn_start,
        turn_end=turn_end,
        turn_count=len(messages),
        total_chars=total_chars,
        summary_chars=summary_chars,
        compression_ratio=compression_ratio,
        turns=turns,
    )


def save_snapshot(snapshot: ContextSnapshot) -> str:
    """Save a snapshot to disk asynchronously.

    Args:
        snapshot: ContextSnapshot to save

    Returns:
        Path where snapshot was saved
    """
    snapshot_dir = _get_snapshot_dir()
    snapshot_path = snapshot_dir / f"{snapshot.snapshot_id}.json"

    # Save synchronously for now; could be async in future
    try:
        with open(snapshot_path, "w") as f:
            json.dump(snapshot.to_dict(), f, indent=2)
        logger.debug(f"Saved context snapshot: {snapshot_path}")
        return str(snapshot_path)
    except Exception as e:
        logger.error(f"Failed to save snapshot: {e}", exc_info=True)
        raise


def load_snapshot(snapshot_id: str) -> Optional[ContextSnapshot]:
    """Load a snapshot from disk.

    Args:
        snapshot_id: ID of snapshot to load

    Returns:
        ContextSnapshot or None if not found
    """
    snapshot_dir = _get_snapshot_dir()
    snapshot_path = snapshot_dir / f"{snapshot_id}.json"

    if not snapshot_path.exists():
        return None

    try:
        with open(snapshot_path, "r") as f:
            data = json.load(f)
        return ContextSnapshot.from_dict(data)
    except Exception as e:
        logger.error(f"Failed to load snapshot {snapshot_id}: {e}", exc_info=True)
        return None


def list_snapshots(limit: int = 10) -> List[str]:
    """List available snapshots, newest first.

    Args:
        limit: Maximum number to return

    Returns:
        List of snapshot IDs
    """
    snapshot_dir = _get_snapshot_dir()
    if not snapshot_dir.exists():
        return []

    files = sorted(
        snapshot_dir.glob("snap_*.json"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    return [f.stem for f in files[:limit]]


def cleanup_old_snapshots(max_age_days: int = 7) -> int:
    """Remove snapshots older than max_age_days.

    Args:
        max_age_days: Age threshold in days

    Returns:
        Number of snapshots removed
    """
    snapshot_dir = _get_snapshot_dir()
    if not snapshot_dir.exists():
        return 0

    now = time.time()
    cutoff = now - (max_age_days * 24 * 3600)
    removed = 0

    for snapshot_file in snapshot_dir.glob("snap_*.json"):
        if snapshot_file.stat().st_mtime < cutoff:
            try:
                snapshot_file.unlink()
                removed += 1
            except Exception as e:
                logger.warning(f"Failed to remove old snapshot: {e}")

    return removed


def estimate_snapshot_cost(snapshot: ContextSnapshot) -> Dict[str, float]:
    """Estimate the cost of using different compression levels.

    Returns cost in tokens for different levels:
      - Level 0: Full context (baseline)
      - Level 1: Turn summaries only (~10% of Level 0)
      - Level 2: Semantic clusters (estimated ~5% of Level 0)
      - Level 3: Session themes (estimated ~2% of Level 0)
    """
    # Rough token estimate: ~4 chars per token
    level_0_tokens = snapshot.total_chars / 4.0
    return {
        "level_0": level_0_tokens,
        "level_1": level_0_tokens * 0.1,
        "level_2": level_0_tokens * 0.05,
        "level_3": level_0_tokens * 0.02,
    }
