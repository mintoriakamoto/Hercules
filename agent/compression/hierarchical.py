"""Hierarchical compression — multi-level context with variable costs.

This module organizes context into 4 levels with different token costs:

  - Level 0: Raw conversation (current window) — 0 tokens
  - Level 1: Turn summaries (every 3 turns) — ~10% of original
  - Level 2: Semantic clusters (every 10 turns) — ~5% of original
  - Level 3: Session themes (end of session) — ~2% of original

The hierarchy enables efficient queries:
  - fetch_context_level(0, query) → full context (expensive)
  - fetch_context_level(1, query) → summaries only (efficient)
  - fetch_context_level(2, query) → clustered summaries (very efficient)
  - fetch_context_level(3, query) → session overview (minimal)

Similarity matching uses simple keyword overlap; production would use embeddings.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# How many turns before creating a cluster summary
CLUSTER_INTERVAL = 10
# How many turns before creating a session theme summary
THEME_INTERVAL = 30


@dataclass
class ContextLevel:
    """A single level in the hierarchical context."""

    level: int  # 0-3
    name: str  # e.g., "full_context", "summaries", "clusters", "themes"
    estimated_cost: float  # Relative cost in tokens
    turns: List[Dict[str, Any]]  # Messages or summaries
    metadata: Dict[str, Any]  # Additional info


def extract_keywords(text: str, max_keywords: int = 10) -> Set[str]:
    """Extract simple keywords from text.

    Production would use NLP/embeddings; this is a baseline.

    Args:
        text: Text to extract from
        max_keywords: Maximum keywords to return

    Returns:
        Set of keyword strings
    """
    # Simple keyword extraction: words > 3 chars, not common
    stop_words = {
        "the", "and", "for", "that", "this", "from", "with", "have",
        "been", "are", "was", "will", "would", "could", "should", "but",
        "not", "can", "has", "had", "what", "when", "where", "which",
        "who", "why", "how", "is", "a", "an", "or", "to", "in", "on",
        "at", "by", "of", "about", "into", "through", "during", "code",
        "use", "using", "used", "get", "set", "make", "create", "do",
    }

    words = text.lower().split()
    keywords = {
        w.strip(".,!?;:") for w in words
        if len(w) > 3 and w.lower() not in stop_words
    }
    return keywords


def calculate_similarity(
    query_keywords: Set[str],
    content_keywords: Set[str],
) -> float:
    """Calculate similarity between two sets of keywords.

    Args:
        query_keywords: Keywords from query
        content_keywords: Keywords from content

    Returns:
        Similarity score 0.0-1.0
    """
    if not query_keywords or not content_keywords:
        return 0.0

    overlap = len(query_keywords & content_keywords)
    union = len(query_keywords | content_keywords)
    return overlap / union if union > 0 else 0.0


def create_level_0(messages: List[Dict[str, Any]]) -> ContextLevel:
    """Create Level 0: Raw conversation (full context).

    Args:
        messages: Full list of messages

    Returns:
        ContextLevel with estimated cost 0 (baseline/reference)
    """
    return ContextLevel(
        level=0,
        name="full_context",
        estimated_cost=1.0,  # Baseline (full context)
        turns=messages,
        metadata={
            "message_count": len(messages),
            "char_count": sum(len(str(m.get("content", ""))) for m in messages),
        },
    )


def create_level_1(messages: List[Dict[str, Any]]) -> ContextLevel:
    """Create Level 1: Turn summaries every 3 turns.

    Args:
        messages: Full list of messages

    Returns:
        ContextLevel with summaries (~10% cost)
    """
    summaries = []
    for i in range(0, len(messages), 3):
        batch = messages[i : i + 3]
        summary_msg = {
            "role": "summary",
            "turn_indices": list(range(i, min(i + 3, len(messages)))),
            "content": _summarize_batch(batch),
            "keywords": list(extract_keywords(_summarize_batch(batch))),
        }
        summaries.append(summary_msg)

    return ContextLevel(
        level=1,
        name="summaries",
        estimated_cost=0.1,  # ~10% of full context
        turns=summaries,
        metadata={
            "summary_count": len(summaries),
            "original_count": len(messages),
            "ratio": len(summaries) / len(messages) if messages else 0,
        },
    )


def create_level_2(messages: List[Dict[str, Any]]) -> ContextLevel:
    """Create Level 2: Semantic clusters every 10 turns.

    Args:
        messages: Full list of messages

    Returns:
        ContextLevel with clustered summaries (~5% cost)
    """
    clusters = []
    for i in range(0, len(messages), CLUSTER_INTERVAL):
        batch = messages[i : i + CLUSTER_INTERVAL]
        cluster_summary = _summarize_batch(batch)
        cluster_msg = {
            "role": "cluster",
            "turn_indices": list(range(i, min(i + CLUSTER_INTERVAL, len(messages)))),
            "content": cluster_summary,
            "keywords": list(extract_keywords(cluster_summary)),
            "topics": _extract_topics(batch),
        }
        clusters.append(cluster_msg)

    return ContextLevel(
        level=2,
        name="clusters",
        estimated_cost=0.05,  # ~5% of full context
        turns=clusters,
        metadata={
            "cluster_count": len(clusters),
            "original_count": len(messages),
            "cluster_size": CLUSTER_INTERVAL,
        },
    )


def create_level_3(messages: List[Dict[str, Any]]) -> ContextLevel:
    """Create Level 3: Session themes (end-of-session summary).

    Args:
        messages: Full list of messages

    Returns:
        ContextLevel with themes (~2% cost)
    """
    session_summary = _summarize_batch(messages, max_length=300)
    all_topics = _extract_topics(messages)
    all_keywords = extract_keywords(
        " ".join(m.get("content", "") for m in messages if isinstance(m.get("content"), str))
    )

    theme_msg = {
        "role": "theme",
        "content": session_summary,
        "keywords": list(all_keywords)[:20],
        "topics": all_topics[:10],
        "message_count": len(messages),
        "turn_range": [0, len(messages) - 1],
    }

    return ContextLevel(
        level=3,
        name="themes",
        estimated_cost=0.02,  # ~2% of full context
        turns=[theme_msg],
        metadata={
            "unique_keywords": len(all_keywords),
            "unique_topics": len(all_topics),
            "total_messages": len(messages),
        },
    )


def build_hierarchy(messages: List[Dict[str, Any]]) -> Dict[int, ContextLevel]:
    """Build all 4 levels of the context hierarchy.

    Args:
        messages: Full conversation history

    Returns:
        Dict mapping level (0-3) to ContextLevel
    """
    return {
        0: create_level_0(messages),
        1: create_level_1(messages),
        2: create_level_2(messages),
        3: create_level_3(messages),
    }


def fetch_context_level(
    hierarchy: Dict[int, ContextLevel],
    level: int,
    similarity_query: Optional[str] = None,
    min_similarity: float = 0.3,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Fetch context at a specific level with optional similarity filtering.

    Args:
        hierarchy: Context hierarchy from build_hierarchy()
        level: Level to fetch (0-3)
        similarity_query: Optional query to filter by keyword similarity
        min_similarity: Minimum similarity score to include
        limit: Maximum items to return

    Returns:
        List of context items (messages or summaries) for that level
    """
    if level not in hierarchy:
        raise ValueError(f"Invalid level {level}, must be 0-3")

    context_level = hierarchy[level]
    items = context_level.turns

    # If no query, return everything
    if not similarity_query:
        if limit:
            return items[:limit]
        return items

    # Filter by similarity if query provided
    query_keywords = extract_keywords(similarity_query)
    if not query_keywords:
        # No valid keywords in query, return all
        if limit:
            return items[:limit]
        return items

    # Score and sort items by similarity
    scored_items = []
    for item in items:
        content = item.get("content", "")
        keywords = set(item.get("keywords", []))

        if not keywords and isinstance(content, str):
            keywords = extract_keywords(content)

        similarity = calculate_similarity(query_keywords, keywords)
        if similarity >= min_similarity:
            scored_items.append((similarity, item))

    # Sort by similarity descending
    scored_items.sort(key=lambda x: x[0], reverse=True)
    results = [item for _, item in scored_items]

    if limit:
        return results[:limit]
    return results


def estimate_hierarchy_cost(hierarchy: Dict[int, ContextLevel]) -> Dict[str, float]:
    """Estimate token cost for each level.

    Args:
        hierarchy: Context hierarchy

    Returns:
        Dict mapping level names to estimated token costs
    """
    level_0 = hierarchy[0]
    base_tokens = level_0.metadata.get("char_count", 0) / 4.0  # ~4 chars/token

    return {
        "level_0": base_tokens,
        "level_1": base_tokens * 0.1,
        "level_2": base_tokens * 0.05,
        "level_3": base_tokens * 0.02,
    }


def _summarize_batch(
    messages: List[Dict[str, Any]],
    max_length: int = 200,
) -> str:
    """Create a brief summary of a batch of messages.

    Args:
        messages: Messages to summarize
        max_length: Maximum summary length

    Returns:
        Summary string
    """
    parts = []
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str) and content:
            # Take first sentence or 30 chars
            if "." in content:
                sentence = content.split(".")[0] + "."
            else:
                sentence = content[:30]
            parts.append(sentence.strip())

    summary = " ".join(parts)
    if len(summary) > max_length:
        summary = summary[:max_length - 3] + "..."
    return summary


def _extract_topics(messages: List[Dict[str, Any]]) -> List[str]:
    """Extract main topics from messages.

    Args:
        messages: Messages to analyze

    Returns:
        List of topic strings
    """
    # Simple topic extraction (production would use NLP)
    topic_keywords = {
        "error": "error_handling",
        "bug": "bug_fixing",
        "test": "testing",
        "deploy": "deployment",
        "api": "api_integration",
        "database": "database_work",
        "performance": "optimization",
        "security": "security",
        "feature": "feature_development",
        "refactor": "refactoring",
    }

    topics = set()
    for msg in messages:
        content = str(msg.get("content", "")).lower()
        for keyword, topic in topic_keywords.items():
            if keyword in content:
                topics.add(topic)

    return list(topics)[:10]
