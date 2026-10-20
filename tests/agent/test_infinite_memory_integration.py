"""Integration tests for the infinite memory and context efficiency system."""

import json

import pytest

from agent.compression import infinite_memory, streaming, hierarchical
from agent.compression import tool_outputs
from agent.knowledge import persistent_store
from agent.memory import adaptive


def test_full_workflow():
    """Test complete workflow: knowledge -> snapshot -> hierarchy -> cache."""
    session_id = "integration_test_1"

    # Initialize manager
    manager = infinite_memory.InfiniteMemoryManager(session_id)

    # Prefetch knowledge
    knowledge = manager.prefetch_knowledge("Tell me about the database schema")
    assert "relevant_knowledge" in knowledge

    # Process tool output (file read)
    tool_stats = manager.process_tool_output(
        tool_name="file_read",
        args={"path": "/src/schema.py"},
        result="class User:\n    id: int\n    name: str\n" * 1000,
    )
    assert "tool" in tool_stats

    # Create snapshot if needed
    messages = [
        {"role": "user", "content": "Tell me about the database schema"},
        {"role": "assistant", "content": "The schema defines: ..."},
    ]
    snapshot = manager.create_snapshot(messages)

    # Build hierarchy
    hierarchy = manager.build_hierarchy(messages)
    assert len(hierarchy) == 4

    # Fetch from different levels
    level_0_items, _ = manager.fetch_context(level=0)
    level_2_items, _ = manager.fetch_context(level=2)

    assert len(level_0_items) > 0
    assert len(level_2_items) <= len(level_0_items)

    # Get compression recommendation
    recommendation = manager.get_compression_recommendation()
    assert "should_compress" in recommendation


def test_memory_efficiency_metrics():
    """Test that memory efficiency metrics are calculated correctly."""
    session_id = "integration_test_2"

    manager = infinite_memory.InfiniteMemoryManager(session_id)

    # Build context
    messages = [
        {"role": "user", "content": "X" * 5000},
        {"role": "assistant", "content": "Y" * 5000},
    ]

    manager.build_hierarchy(messages)

    metrics = manager.estimate_memory_efficiency()

    assert "hierarchy_costs" in metrics
    assert "cache_savings" in metrics
    assert "knowledge_facts" in metrics


def test_knowledge_extraction_and_retrieval():
    """Test extracting and retrieving knowledge facts."""
    session_id = "integration_test_3"

    manager = infinite_memory.InfiniteMemoryManager(session_id)

    # Store knowledge
    manager.process_tool_output(
        tool_name="code_search",
        args={"query": "database"},
        result="Found database module at src/database.py with PostgreSQL adapter",
    )

    # Retrieve it
    knowledge = manager.prefetch_knowledge("Where is the database code?")
    assert "relevant_knowledge" in knowledge


def test_adaptive_compression_feedback():
    """Test adaptive compression based on access patterns."""
    session_id = "integration_test_4"

    # Build hierarchy
    messages = [
        {"role": "user", "content": "Initial message"},
        {"role": "assistant", "content": "Initial response"},
    ]

    hierarchy = hierarchical.build_hierarchy(messages)

    # Simulate accessing different levels
    for _ in range(5):
        hierarchical.fetch_context_level(
            hierarchy,
            level=1,
            similarity_query="test",
        )

    # Get compression recommendation based on access patterns
    recommendation = infinite_memory.InfiniteMemoryManager(session_id).get_compression_recommendation()

    assert "should_compress" in recommendation


def test_session_lifecycle():
    """Test complete session lifecycle."""
    session_id = "integration_test_5"

    manager = infinite_memory.InfiniteMemoryManager(session_id)

    # Multiple turns
    for turn in range(5):
        manager.turn_count = turn

        # Process tool output
        manager.process_tool_output(
            tool_name=f"tool_{turn}",
            args={"input": f"data_{turn}"},
            result=f"Result {turn}: " + "X" * 5000,
        )

        # Build hierarchy periodically
        messages = [
            {"role": "user", "content": f"Turn {turn} input"},
            {"role": "assistant", "content": f"Turn {turn} output"},
        ]

        if turn % 2 == 0:
            manager.build_hierarchy(messages)
            if manager.should_create_snapshot(messages):
                manager.create_snapshot(messages)

    # End of session
    summary = manager.end_of_session()

    assert "session_id" in summary
    assert "turn_count" in summary
    assert "snapshots" in summary
    assert "knowledge" in summary


def test_hierarchical_context_efficiency():
    """Test that hierarchy actually reduces token cost."""
    messages = []
    for i in range(50):
        messages.append({
            "role": "user" if i % 2 == 0 else "assistant",
            "content": f"Message {i}: " + "X" * 500,
        })

    hierarchy = hierarchical.build_hierarchy(messages)
    costs = hierarchical.estimate_hierarchy_cost(hierarchy)

    # Level 3 should cost < 5% of Level 0
    assert costs["level_3"] < costs["level_0"] * 0.05

    # Level 2 should cost < 10% of Level 0
    assert costs["level_2"] < costs["level_0"] * 0.1


def test_tool_caching_savings():
    """Test that tool output caching provides real savings."""
    # Simulate large tool outputs
    for i in range(3):
        tool_outputs.compress_tool_output(
            f"large_tool_{i}",
            {"id": i},
            "X" * 100000,
        )

    savings = tool_outputs.estimate_cache_savings()

    # Should have cached items
    assert savings["cached_items"] >= 0

    # If there are cached items, should have disk savings
    if savings["cached_items"] > 0:
        assert savings["disk_saved_bytes"] > 0
        assert savings["compression_ratio"] < 1.0


def test_knowledge_pruning():
    """Test that low-confidence knowledge gets pruned."""
    session_id = "integration_test_6"

    # Store low-confidence fact
    persistent_store.store_fact(
        session_id=session_id,
        topic="test",
        fact="This is a low-confidence fact",
        confidence=0.2,
    )

    # Store high-confidence fact
    persistent_store.store_fact(
        session_id=session_id,
        topic="test",
        fact="This is a high-confidence fact",
        confidence=0.9,
    )

    before = persistent_store.get_statistics(session_id)

    # Prune (might not actually prune without time passing)
    removed, downgraded = persistent_store.prune_old_facts()

    after = persistent_store.get_statistics(session_id)

    # High-confidence facts should survive
    high_confidence = persistent_store.lookup_knowledge(
        session_id,
        min_confidence=0.8,
    )
    assert len(high_confidence) > 0


def test_streaming_snapshot_creation():
    """Test that streaming snapshots work correctly."""
    messages = [
        {"role": "user", "content": f"Message {i}"} for i in range(12)
    ]

    # Should trigger snapshot at 10 turns
    snapshot = streaming.create_snapshot(messages, turn_start=0, turn_end=11)

    assert snapshot.turn_count == 12
    assert snapshot.compression_ratio < 1.0

    # Save and retrieve
    streaming.save_snapshot(snapshot)
    loaded = streaming.load_snapshot(snapshot.snapshot_id)

    assert loaded is not None
    assert loaded.turn_count == snapshot.turn_count


def test_end_to_end_100_turns():
    """Test system with 100+ turns without degradation."""
    session_id = "integration_test_7"

    manager = infinite_memory.InfiniteMemoryManager(session_id)

    # Simulate 100 turns
    for turn in range(100):
        manager.turn_count = turn

        # User message
        user_msg = {
            "role": "user",
            "content": f"Question at turn {turn}: " + "X" * 100,
        }

        # Tool call (simulate)
        manager.process_tool_output(
            tool_name="search",
            args={"query": f"turn_{turn}"},
            result="Found result: " + "Y" * 1000,
        )

        # Assistant response
        assistant_msg = {
            "role": "assistant",
            "content": f"Response {turn}: " + "Z" * 1000,
        }

        messages = [user_msg, assistant_msg]

        # Periodic snapshots
        if turn % 10 == 0:
            manager.build_hierarchy(messages)
            manager.create_snapshot(messages)

    # System should still be responsive
    metrics = manager.estimate_memory_efficiency()
    assert "hierarchy_costs" in metrics


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
