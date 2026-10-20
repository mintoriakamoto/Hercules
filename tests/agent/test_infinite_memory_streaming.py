"""Tests for streaming context compaction module."""

import json
import tempfile
from pathlib import Path

import pytest

from agent.compression import streaming


def test_turn_snapshot_creation():
    """Test creating snapshots of individual turns."""
    message = {
        "role": "user",
        "content": "This is a test message about fixing a bug in the code.",
    }

    summary = streaming._summarize_message(message)
    assert len(summary) > 0
    assert len(summary) <= 100


def test_snapshot_triggers():
    """Test conditions that trigger snapshot creation."""
    # Every 5 turns
    assert streaming.should_snapshot(turn_count=5, total_chars=1000)
    assert not streaming.should_snapshot(turn_count=4, total_chars=1000)

    # Every 50k characters
    assert streaming.should_snapshot(turn_count=2, total_chars=50000)
    assert not streaming.should_snapshot(turn_count=2, total_chars=40000)


def test_context_snapshot_creation():
    """Test creating a complete context snapshot."""
    messages = [
        {
            "role": "user",
            "content": "What is the sum of 2 + 2?",
        },
        {
            "role": "assistant",
            "content": "The sum of 2 + 2 is 4.",
        },
        {
            "role": "user",
            "content": "What about 5 + 5?",
        },
    ]

    snapshot = streaming.create_snapshot(messages, turn_start=0, turn_end=2)

    assert snapshot.turn_count == 3
    assert snapshot.total_chars > 0
    assert snapshot.compression_ratio < 1.0
    assert len(snapshot.turns) == 3
    assert snapshot.turns[0].role == "user"
    assert snapshot.turns[1].role == "assistant"


def test_snapshot_serialization():
    """Test snapshot to_dict and from_dict roundtrip."""
    messages = [
        {
            "role": "user",
            "content": "Test message with some content here.",
        },
    ]

    snapshot = streaming.create_snapshot(messages)
    data = snapshot.to_dict()

    # Verify structure
    assert "version" in data
    assert "snapshot_id" in data
    assert "turns" in data
    assert len(data["turns"]) == 1

    # Roundtrip
    reconstructed = streaming.ContextSnapshot.from_dict(data)
    assert reconstructed.snapshot_id == snapshot.snapshot_id
    assert reconstructed.turn_count == snapshot.turn_count


def test_snapshot_storage_and_retrieval(tmp_path):
    """Test saving and loading snapshots."""
    messages = [
        {
            "role": "user",
            "content": "Testing snapshot persistence with some content.",
        },
    ]

    snapshot = streaming.create_snapshot(messages)

    # Save snapshot
    path = streaming.save_snapshot(snapshot)
    assert Path(path).exists()

    # Load snapshot
    loaded = streaming.load_snapshot(snapshot.snapshot_id)
    assert loaded is not None
    assert loaded.snapshot_id == snapshot.snapshot_id
    assert loaded.turn_count == snapshot.turn_count


def test_snapshot_compression_ratio():
    """Test compression ratio calculation."""
    # Large messages
    messages = [
        {
            "role": "user",
            "content": "A" * 1000,  # 1000 char message
        },
        {
            "role": "assistant",
            "content": "B" * 2000,  # 2000 char message
        },
    ]

    snapshot = streaming.create_snapshot(messages)

    # Compression should reduce size significantly
    assert snapshot.total_chars == 3000
    assert snapshot.summary_chars < snapshot.total_chars
    assert 0 < snapshot.compression_ratio < 1


def test_snapshot_cost_estimation():
    """Test cost estimation for different compression levels."""
    messages = [
        {
            "role": "user",
            "content": "A" * 4000,  # ~1000 tokens
        },
    ]

    snapshot = streaming.create_snapshot(messages)
    costs = streaming.estimate_snapshot_cost(snapshot)

    assert "level_0" in costs
    assert "level_1" in costs
    assert "level_2" in costs
    assert "level_3" in costs

    # Each level should cost less than the previous
    assert costs["level_3"] < costs["level_2"]
    assert costs["level_2"] < costs["level_1"]
    assert costs["level_1"] < costs["level_0"]


def test_topic_extraction():
    """Test key topic extraction from messages."""
    message = {
        "role": "user",
        "content": "Found a critical bug in the error handling code. Need to fix this immediately.",
    }

    topics = streaming._extract_turn_topics(message)
    assert isinstance(topics, list)
    # Should find at least "error" and "bug" and "code"
    topics_lower = [t.lower() for t in topics]
    assert any(t in topics_lower for t in ["error", "bug", "code"])


def test_list_snapshots():
    """Test listing available snapshots."""
    # Save a couple of snapshots
    messages = [
        {
            "role": "user",
            "content": "Test content",
        },
    ]

    snapshot1 = streaming.create_snapshot(messages)
    streaming.save_snapshot(snapshot1)

    snapshot2 = streaming.create_snapshot(messages)
    streaming.save_snapshot(snapshot2)

    snapshots = streaming.list_snapshots(limit=10)
    assert len(snapshots) >= 2
    # Should be newest first
    assert snapshots[0] == snapshot2.snapshot_id or snapshots[0] == snapshot1.snapshot_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
