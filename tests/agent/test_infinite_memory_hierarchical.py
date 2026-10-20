"""Tests for hierarchical compression module."""

import pytest

from agent.compression import hierarchical


def test_keyword_extraction():
    """Test keyword extraction from text."""
    text = "This is a test message about fixing bugs in the database code."

    keywords = hierarchical.extract_keywords(text)
    assert isinstance(keywords, set)
    assert len(keywords) > 0
    assert "test" in keywords or "message" in keywords


def test_keyword_extraction_filters_stopwords():
    """Test that stopwords are filtered out."""
    text = "the and or is a to from with have been"

    keywords = hierarchical.extract_keywords(text)
    # Most of these should be filtered as stopwords
    assert len(keywords) == 0 or all(kw not in ["the", "and", "or", "is", "a"] for kw in keywords)


def test_similarity_calculation():
    """Test keyword similarity scoring."""
    keywords1 = {"bug", "fix", "code"}
    keywords2 = {"bug", "error", "fix"}

    similarity = hierarchical.calculate_similarity(keywords1, keywords2)
    assert 0.0 <= similarity <= 1.0
    # Should be fairly similar (2 out of 4 unique keywords overlap)
    assert similarity > 0.4


def test_similarity_empty_sets():
    """Test similarity with empty keyword sets."""
    assert hierarchical.calculate_similarity(set(), {"a", "b"}) == 0.0
    assert hierarchical.calculate_similarity({"a", "b"}, set()) == 0.0
    assert hierarchical.calculate_similarity(set(), set()) == 0.0


def test_level_0_full_context():
    """Test Level 0: full context preservation."""
    messages = [
        {"role": "user", "content": "Message 1"},
        {"role": "assistant", "content": "Response 1"},
        {"role": "user", "content": "Message 2"},
    ]

    level_0 = hierarchical.create_level_0(messages)

    assert level_0.level == 0
    assert level_0.estimated_cost == 1.0
    assert len(level_0.turns) == 3
    assert level_0.metadata["message_count"] == 3


def test_level_1_summaries():
    """Test Level 1: turn summaries."""
    messages = [
        {"role": "user", "content": "First message about testing."},
        {"role": "assistant", "content": "First response."},
        {"role": "user", "content": "Second message."},
        {"role": "assistant", "content": "Second response."},
        {"role": "user", "content": "Third message."},
        {"role": "assistant", "content": "Third response."},
    ]

    level_1 = hierarchical.create_level_1(messages)

    assert level_1.level == 1
    assert level_1.estimated_cost == 0.1
    assert len(level_1.turns) >= 2  # Should group into ~2 summaries
    assert all(s.get("role") == "summary" for s in level_1.turns)


def test_level_2_clusters():
    """Test Level 2: semantic clusters."""
    messages = [
        {"role": "user", "content": f"Message {i}."} for i in range(15)
    ]

    level_2 = hierarchical.create_level_2(messages)

    assert level_2.level == 2
    assert level_2.estimated_cost == 0.05
    assert len(level_2.turns) >= 1
    assert all(c.get("role") == "cluster" for c in level_2.turns)


def test_level_3_themes():
    """Test Level 3: session themes."""
    messages = [
        {"role": "user", "content": "Discussing error handling in the codebase."},
        {"role": "assistant", "content": "Let me help with error handling."},
        {"role": "user", "content": "Also need database optimization."},
    ]

    level_3 = hierarchical.create_level_3(messages)

    assert level_3.level == 3
    assert level_3.estimated_cost == 0.02
    assert len(level_3.turns) == 1
    assert level_3.turns[0].get("role") == "theme"
    assert "keywords" in level_3.turns[0]
    assert "topics" in level_3.turns[0]


def test_build_hierarchy():
    """Test building complete 4-level hierarchy."""
    messages = [
        {"role": "user", "content": "Test message about code quality."},
        {"role": "assistant", "content": "I can help with code quality improvements."},
    ]

    hierarchy = hierarchical.build_hierarchy(messages)

    assert len(hierarchy) == 4
    assert all(i in hierarchy for i in range(4))
    assert hierarchy[0].level == 0
    assert hierarchy[1].level == 1
    assert hierarchy[2].level == 2
    assert hierarchy[3].level == 3


def test_fetch_context_all_levels():
    """Test fetching context at different levels."""
    messages = [
        {"role": "user", "content": "Question about database performance"},
        {"role": "assistant", "content": "Database optimization suggestions"},
    ]

    hierarchy = hierarchical.build_hierarchy(messages)

    # Fetch at each level
    for level in range(4):
        items = hierarchical.fetch_context_level(hierarchy, level)
        assert isinstance(items, list)
        assert len(items) > 0


def test_fetch_context_with_query():
    """Test fetching context with similarity query."""
    messages = [
        {"role": "user", "content": "Discussing database performance issues"},
        {"role": "assistant", "content": "Optimization strategies"},
        {"role": "user", "content": "Completely different topic now"},
    ]

    hierarchy = hierarchical.build_hierarchy(messages)

    # Query for database-related content
    items = hierarchical.fetch_context_level(
        hierarchy,
        level=2,
        similarity_query="database performance",
    )

    assert isinstance(items, list)
    # Should find relevant items


def test_fetch_context_with_limit():
    """Test fetching limited context."""
    messages = [
        {"role": "user", "content": f"Message {i}."}
        for i in range(20)
    ]

    hierarchy = hierarchical.build_hierarchy(messages)

    items = hierarchical.fetch_context_level(
        hierarchy,
        level=1,
        limit=3,
    )

    assert len(items) <= 3


def test_hierarchy_cost_estimation():
    """Test cost estimation for hierarchy."""
    messages = [
        {"role": "user", "content": "A" * 4000},  # ~1000 tokens
    ]

    hierarchy = hierarchical.build_hierarchy(messages)
    costs = hierarchical.estimate_hierarchy_cost(hierarchy)

    assert "level_0" in costs
    assert "level_1" in costs
    assert "level_2" in costs
    assert "level_3" in costs

    # Each should cost progressively less
    assert costs["level_3"] < costs["level_2"]
    assert costs["level_2"] < costs["level_1"]
    assert costs["level_1"] < costs["level_0"]


def test_topic_extraction():
    """Test topic extraction from messages."""
    messages = [
        {"role": "user", "content": "There's an error in the database code causing performance issues."},
        {"role": "assistant", "content": "Let's deploy a fix and run tests."},
    ]

    topics = hierarchical._extract_topics(messages)
    assert isinstance(topics, list)
    # Should find error, database, performance, deploy, test related topics


def test_invalid_level():
    """Test error handling for invalid compression levels."""
    messages = [
        {"role": "user", "content": "Test"},
    ]
    hierarchy = hierarchical.build_hierarchy(messages)

    with pytest.raises(ValueError):
        hierarchical.fetch_context_level(hierarchy, level=5)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
