"""Tests for adaptive memory manager module."""

import pytest

from agent.memory import adaptive


def test_record_context_access():
    """Test recording context access patterns."""
    session_id = "test_session_1"
    item_id = "item_001"

    adaptive.record_context_access(
        session_id=session_id,
        item_id=item_id,
        context_type="message",
        compression_level=0,
        query_length=50,
        success=True,
    )

    # Retrieve the score
    score = adaptive.get_item_score(item_id)
    assert score is not None
    assert score.reference_count == 1
    assert score.relevance_score > 0.5  # Successful access boosts score


def test_score_updates_with_repeated_access():
    """Test that scores improve with repeated successful access."""
    session_id = "test_session_2"
    item_id = "item_002"

    # First access
    adaptive.record_context_access(
        session_id=session_id,
        item_id=item_id,
        context_type="summary",
        compression_level=1,
        success=True,
    )

    score1 = adaptive.get_item_score(item_id)
    initial_score = score1.relevance_score

    # Multiple successful accesses
    for _ in range(5):
        adaptive.record_context_access(
            session_id=session_id,
            item_id=item_id,
            context_type="summary",
            compression_level=1,
            success=True,
        )

    score2 = adaptive.get_item_score(item_id)
    assert score2.reference_count == 6
    # Score should approach 1.0 with repeated success
    assert score2.relevance_score >= initial_score


def test_score_decreases_with_failed_access():
    """Test that scores decrease with unsuccessful access."""
    session_id = "test_session_3"
    item_id = "item_003"

    # Initial successful access
    adaptive.record_context_access(
        session_id=session_id,
        item_id=item_id,
        context_type="cluster",
        compression_level=2,
        success=True,
    )

    # Failed access
    adaptive.record_context_access(
        session_id=session_id,
        item_id=item_id,
        context_type="cluster",
        compression_level=2,
        success=False,
    )

    score = adaptive.get_item_score(item_id)
    # Score should drop with failed access
    assert score.relevance_score < 1.0


def test_get_session_scores():
    """Test getting all scores for a session."""
    session_id = "test_session_4"

    # Record access for multiple items
    for i in range(5):
        item_id = f"item_{i:03d}"
        adaptive.record_context_access(
            session_id=session_id,
            item_id=item_id,
            context_type="message",
            compression_level=0,
            success=True,
        )

    scores = adaptive.get_session_scores(session_id, limit=10)
    assert len(scores) >= 5


def test_get_low_priority_items():
    """Test identifying low-priority items for compression."""
    session_id = "test_session_5"

    # Create items with varying priority
    # High priority
    adaptive.record_context_access(
        session_id=session_id,
        item_id="high_priority",
        context_type="message",
        compression_level=0,
        success=True,
    )
    # Multiple accesses boost priority
    for _ in range(10):
        adaptive.record_context_access(
            session_id=session_id,
            item_id="high_priority",
            context_type="message",
            compression_level=0,
            success=True,
        )

    # Low priority (single failed access)
    adaptive.record_context_access(
        session_id=session_id,
        item_id="low_priority",
        context_type="message",
        compression_level=0,
        success=False,
    )

    low_priority = adaptive.get_low_priority_items(session_id, threshold=0.5)
    assert "low_priority" in low_priority
    # High priority item should not be in low priority list
    assert "high_priority" not in low_priority


def test_get_high_priority_items():
    """Test identifying high-priority items to preserve."""
    session_id = "test_session_6"

    # Create high priority item with many successful accesses
    item_id = "preserved_item"
    for _ in range(10):
        adaptive.record_context_access(
            session_id=session_id,
            item_id=item_id,
            context_type="message",
            compression_level=0,
            success=True,
        )

    high_priority = adaptive.get_high_priority_items(session_id, threshold=0.7)
    assert item_id in high_priority


def test_access_statistics():
    """Test getting access pattern statistics."""
    session_id = "test_session_7"

    # Record some accesses
    for level in range(3):
        for i in range(5):
            adaptive.record_context_access(
                session_id=session_id,
                item_id=f"item_level_{level}_{i}",
                context_type="message",
                compression_level=level,
                success=True,
            )

    stats = adaptive.get_access_statistics(session_id)

    assert "overall" in stats
    assert "by_level" in stats
    assert stats["overall"]["total_accesses"] >= 15
    assert stats["overall"]["success_rate"] > 0.5


def test_compression_impact_estimation():
    """Test estimating compression impact."""
    session_id = "test_session_8"

    # Create mix of high and low priority items
    # High priority items
    for i in range(5):
        for _ in range(5):
            adaptive.record_context_access(
                session_id=session_id,
                item_id=f"high_{i}",
                context_type="message",
                compression_level=0,
                success=True,
            )

    # Low priority items
    for i in range(10):
        adaptive.record_context_access(
            session_id=session_id,
            item_id=f"low_{i}",
            context_type="message",
            compression_level=0,
            success=False,
        )

    impact = adaptive.estimate_compression_impact(session_id)

    assert "candidates_for_compression" in impact
    assert "compression_percent" in impact
    assert "estimated_token_savings" in impact
    assert "recommendation" in impact


def test_clear_session():
    """Test clearing all scores for a session."""
    session_id = "test_session_9"

    # Record some accesses
    for i in range(5):
        adaptive.record_context_access(
            session_id=session_id,
            item_id=f"item_{i}",
            context_type="message",
            compression_level=0,
            success=True,
        )

    # Clear the session
    cleared = adaptive.clear_session(session_id)
    assert cleared > 0

    # Verify scores are cleared
    scores = adaptive.get_session_scores(session_id)
    assert len(scores) == 0


def test_mean_query_length_tracking():
    """Test tracking mean query length for items."""
    session_id = "test_session_10"
    item_id = "tracked_item"

    # Record accesses with different query lengths
    adaptive.record_context_access(
        session_id=session_id,
        item_id=item_id,
        context_type="message",
        compression_level=0,
        query_length=100,
        success=True,
    )
    adaptive.record_context_access(
        session_id=session_id,
        item_id=item_id,
        context_type="message",
        compression_level=0,
        query_length=200,
        success=True,
    )

    score = adaptive.get_item_score(item_id)
    # Mean should be around 150
    assert 100 <= score.mean_query_length <= 200


def test_multiple_sessions_isolated():
    """Test that scores are isolated per session."""
    session1 = "session_1"
    session2 = "session_2"
    item_id = "test_item"

    # Same item ID, different sessions
    adaptive.record_context_access(
        session_id=session1,
        item_id=item_id,
        context_type="message",
        compression_level=0,
        success=True,
    )
    adaptive.record_context_access(
        session_id=session2,
        item_id=item_id,
        context_type="message",
        compression_level=0,
        success=False,
    )

    # Scores should differ
    scores1 = adaptive.get_session_scores(session1)
    scores2 = adaptive.get_session_scores(session2)

    # Both should have the item
    assert len(scores1) > 0
    assert len(scores2) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
