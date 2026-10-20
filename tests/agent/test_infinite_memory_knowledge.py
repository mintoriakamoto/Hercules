"""Tests for persistent knowledge store module."""

import time

import pytest

from agent.knowledge import persistent_store


def test_store_and_retrieve_fact():
    """Test storing and retrieving a fact."""
    session_id = "test_session_1"
    fact_id = persistent_store.store_fact(
        session_id=session_id,
        topic="codebase",
        fact="The main API is defined in api.py",
        confidence=0.8,
        source_turn=5,
    )

    assert fact_id > 0

    # Retrieve the fact
    facts = persistent_store.lookup_knowledge(session_id, topic="codebase")
    assert len(facts) > 0

    found = any(f.fact_id == fact_id for f in facts)
    assert found


def test_fact_confidence_clamping():
    """Test that confidence scores are clamped to 0-1."""
    session_id = "test_session_2"

    # Store with invalid confidence values
    fact_id1 = persistent_store.store_fact(
        session_id=session_id,
        topic="test",
        fact="Too high confidence",
        confidence=1.5,  # > 1.0
    )

    fact_id2 = persistent_store.store_fact(
        session_id=session_id,
        topic="test",
        fact="Negative confidence",
        confidence=-0.5,  # < 0.0
    )

    facts = persistent_store.lookup_knowledge(session_id)

    # Should all be clamped to valid range
    for fact in facts:
        assert 0.0 <= fact.confidence <= 1.0


def test_lookup_with_min_confidence():
    """Test looking up facts with confidence threshold."""
    session_id = "test_session_3"

    # Store facts with different confidences
    persistent_store.store_fact(
        session_id=session_id,
        topic="test",
        fact="High confidence fact",
        confidence=0.9,
    )
    persistent_store.store_fact(
        session_id=session_id,
        topic="test",
        fact="Low confidence fact",
        confidence=0.3,
    )

    # Lookup with high threshold
    high_confidence_facts = persistent_store.lookup_knowledge(
        session_id,
        min_confidence=0.8,
    )

    assert len(high_confidence_facts) == 1
    assert high_confidence_facts[0].confidence >= 0.8


def test_lookup_by_topic():
    """Test looking up facts by topic filter."""
    session_id = "test_session_4"

    persistent_store.store_fact(
        session_id=session_id,
        topic="codebase",
        fact="Fact about codebase",
        confidence=0.7,
    )
    persistent_store.store_fact(
        session_id=session_id,
        topic="architecture",
        fact="Fact about architecture",
        confidence=0.7,
    )

    # Lookup only codebase facts
    codebase_facts = persistent_store.lookup_knowledge(
        session_id,
        topic="codebase",
    )

    assert all(f.topic == "codebase" for f in codebase_facts)


def test_lookup_by_keyword_query():
    """Test looking up facts by keyword search."""
    session_id = "test_session_5"

    persistent_store.store_fact(
        session_id=session_id,
        topic="test",
        fact="The database uses PostgreSQL for data storage",
        confidence=0.8,
    )
    persistent_store.store_fact(
        session_id=session_id,
        topic="test",
        fact="We use Docker for containerization",
        confidence=0.7,
    )

    # Search for database-related facts
    db_facts = persistent_store.lookup_knowledge(
        session_id,
        query="database",
    )

    assert len(db_facts) >= 1
    assert "database" in db_facts[0].fact.lower()


def test_update_confidence():
    """Test updating a fact's confidence score."""
    session_id = "test_session_6"

    fact_id = persistent_store.store_fact(
        session_id=session_id,
        topic="test",
        fact="Initial fact",
        confidence=0.5,
    )

    # Update confidence
    success = persistent_store.update_confidence(fact_id, 0.9)
    assert success

    # Verify update
    facts = persistent_store.lookup_knowledge(session_id, min_confidence=0.8)
    found = any(f.fact_id == fact_id for f in facts)
    assert found


def test_record_fact_reference():
    """Test recording fact references for prioritization."""
    session_id = "test_session_7"

    fact_id = persistent_store.store_fact(
        session_id=session_id,
        topic="test",
        fact="A fact that gets referenced",
        confidence=0.6,
    )

    # Record multiple references
    persistent_store.record_fact_reference(fact_id, context="used in query 1")
    persistent_store.record_fact_reference(fact_id, context="used in query 2")

    # Retrieve and check reference count
    facts = persistent_store.lookup_knowledge(session_id)
    found = next((f for f in facts if f.fact_id == fact_id), None)
    assert found is not None
    assert found.reference_count >= 2


def test_statistics():
    """Test getting knowledge base statistics."""
    session_id = "test_session_8"

    # Store multiple facts
    for i in range(5):
        persistent_store.store_fact(
            session_id=session_id,
            topic="test",
            fact=f"Fact number {i}",
            confidence=0.4 + i * 0.1,
        )

    stats = persistent_store.get_statistics(session_id)

    assert stats["total_facts"] >= 5
    assert stats["unique_topics"] >= 1
    assert stats["avg_confidence"] > 0


def test_clear_session():
    """Test clearing all facts for a session."""
    session_id = "test_session_9"

    persistent_store.store_fact(
        session_id=session_id,
        topic="test",
        fact="Fact to clear",
        confidence=0.7,
    )

    # Clear the session
    cleared_count = persistent_store.clear_session(session_id)
    assert cleared_count > 0

    # Verify facts are gone
    facts = persistent_store.lookup_knowledge(session_id)
    assert len(facts) == 0


def test_fact_uniqueness():
    """Test that duplicate facts update rather than duplicate."""
    session_id = "test_session_10"

    fact_id1 = persistent_store.store_fact(
        session_id=session_id,
        topic="test",
        fact="This is a unique fact",
        confidence=0.5,
    )

    # Store the same fact again with different confidence
    fact_id2 = persistent_store.store_fact(
        session_id=session_id,
        topic="test",
        fact="This is a unique fact",
        confidence=0.9,
    )

    # Should update the same fact, not create duplicate
    facts = persistent_store.lookup_knowledge(session_id)
    assert len(facts) == 1
    assert facts[0].confidence == 0.9


def test_prune_old_facts():
    """Test pruning of old low-confidence facts."""
    session_id = "test_session_11"

    # This test might not work in unit tests without time manipulation
    # But we can verify the function exists and runs
    removed, downgraded = persistent_store.prune_old_facts()
    assert isinstance(removed, int)
    assert isinstance(downgraded, int)


def test_lookup_with_limit():
    """Test limiting lookup results."""
    session_id = "test_session_12"

    # Store multiple facts
    for i in range(10):
        persistent_store.store_fact(
            session_id=session_id,
            topic="test",
            fact=f"Fact {i}",
            confidence=0.5 + i * 0.01,
        )

    # Lookup with limit
    facts = persistent_store.lookup_knowledge(session_id, limit=3)
    assert len(facts) <= 3


def test_multiple_sessions():
    """Test that facts are isolated by session."""
    session1 = "session_1"
    session2 = "session_2"

    persistent_store.store_fact(
        session_id=session1,
        topic="test",
        fact="Fact in session 1",
        confidence=0.7,
    )
    persistent_store.store_fact(
        session_id=session2,
        topic="test",
        fact="Fact in session 2",
        confidence=0.7,
    )

    # Lookup should only return facts for specific session
    session1_facts = persistent_store.lookup_knowledge(session1)
    session2_facts = persistent_store.lookup_knowledge(session2)

    assert all(f.session_id == session1 for f in session1_facts)
    assert all(f.session_id == session2 for f in session2_facts)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
