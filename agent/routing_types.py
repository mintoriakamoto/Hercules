"""Shared types and enums for task-aware model routing."""

from enum import Enum


class ModelTier(str, Enum):
    """Which class of model to use for a task.

    This is not a permission gate. It is a capability/cost hint for the
    router and the local quantization picker.
    """

    FAST_CHEAP = "fast_cheap"  # small/fast: Haiku, GPT-4o-mini, local 7B
    BALANCED = "balanced"  # general: Sonnet, GPT-4o, local 14-32B
    CAPABLE = "capable"  # hard reasoning: Opus, o1-class, large local
    EXTENDED = "extended"  # long-horizon research / full-precision local


class TaskCategory(str, Enum):
    """What kind of work the task is."""

    READ = "read"
    ANALYZE = "analyze"
    CODE = "code"
    REASONING = "reasoning"
    RESEARCH = "research"
    SECURITY = "security"


class ReasoningComplexity(str, Enum):
    """How hard the task is, independent of category.

    Used by QuantizationSelector to pick weight/KV precision.
    Higher complexity keeps more bits (better accuracy, more VRAM).
    """

    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    CRITICAL = "critical"
