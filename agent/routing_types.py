"""Shared types and enums for task-aware model routing."""

from enum import Enum


class ModelTier(str, Enum):
    """Model capability tiers for task routing."""

    FAST_CHEAP = "fast_cheap"  # e.g., GPT-4o mini, Claude Haiku — speed/cost focused
    BALANCED = "balanced"  # e.g., Claude Sonnet, GPT-4o — general purpose
    CAPABLE = "capable"  # e.g., Claude Opus, o1 — advanced reasoning
    EXTENDED = "extended"  # e.g., o1-pro — extended thinking, research


class TaskCategory(str, Enum):
    """Task categories for routing decisions."""

    READ = "read"  # Information retrieval, file reading
    ANALYZE = "analyze"  # Analysis, summarization, simple classification
    CODE = "code"  # Programming, code generation, debugging
    REASONING = "reasoning"  # Complex reasoning, planning, design
    RESEARCH = "research"  # Deep research, exploration, comprehensive analysis
    SECURITY = "security"  # Security testing, vulnerability analysis
