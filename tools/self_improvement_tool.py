"""Tool for managing self-improvement of agent skills via CORAL system."""

from __future__ import annotations

from typing import Any, Dict, Optional
from pathlib import Path

from agent.self_improvement_coral import (
    get_improvement_engine,
    ImprovementType,
)


def analyze_skill_performance(skill_name: str) -> Dict[str, Any]:
    """Analyze performance of a specific skill.

    Args:
        skill_name: Name of the skill to analyze

    Returns:
        Dictionary with:
        - skill_name: The analyzed skill
        - success_rate: Recent success rate (0.0-1.0)
        - avg_latency_ms: Average execution time
        - total_runs: Total executions tracked
        - improvement_potential: Estimated improvement opportunity
        - recommendation: Suggested next action

    Examples:
        analyze_skill_performance("read_file")
        analyze_skill_performance("web_search")
    """
    engine = get_improvement_engine()
    metrics = engine.analyze_performance(skill_name)

    if not metrics:
        return {
            "skill_name": skill_name,
            "error": "No performance data available yet",
            "recommendation": "Execute the skill several times to build performance baseline",
        }

    profile = engine._load_or_create_profile(skill_name)
    improvement_potential = 1.0 - metrics.success_rate

    return {
        "skill_name": skill_name,
        "success_rate": round(metrics.success_rate, 3),
        "avg_latency_ms": round(metrics.avg_latency_ms, 2),
        "total_runs": profile.total_runs,
        "improvement_potential": round(improvement_potential, 3),
        "recommendation": _get_recommendation(metrics.success_rate, improvement_potential),
    }


def propose_skill_improvement(
    skill_name: str,
    improvement_type: str = "performance",
    description: str = "",
    expected_improvement: float = 1.1,
) -> Dict[str, Any]:
    """Propose an improvement to a skill.

    Args:
        skill_name: Skill to improve
        improvement_type: Type of improvement (performance, generalization, efficiency, reliability, maintainability)
        description: Description of the proposed improvement
        expected_improvement: Expected improvement ratio (e.g., 1.2 = 20% improvement)

    Returns:
        Dictionary with:
        - skill_name: The skill
        - version: New version number
        - improvement_type: Category of improvement
        - description: The proposed change
        - confidence: Confidence level in the improvement
        - status: Whether proposal was accepted

    Examples:
        propose_skill_improvement("read_file", "efficiency", "Add caching for repeated reads", 1.15)
        propose_skill_improvement("web_search", "reliability", "Add retry logic for timeouts")
    """
    engine = get_improvement_engine()

    try:
        imp_type = ImprovementType[improvement_type.upper()]
    except KeyError:
        return {
            "error": f"Invalid improvement_type. Must be one of: {', '.join(t.value for t in ImprovementType)}",
            "skill_name": skill_name,
        }

    improvement = engine.propose_improvement(
        skill_name=skill_name,
        improvement_type=imp_type,
        description=description or f"Proposed {improvement_type} improvement",
        expected_ratio=expected_improvement,
        confidence=0.7,
    )

    if not improvement:
        return {
            "skill_name": skill_name,
            "error": "Cannot propose improvement without performance baseline",
            "recommendation": "Execute the skill several times first",
        }

    return {
        "skill_name": improvement.skill_name,
        "version": improvement.version,
        "improvement_type": improvement.improvement_type.value,
        "description": improvement.description,
        "expected_improvement_ratio": improvement.improvement_ratio,
        "confidence": round(improvement.confidence, 2),
        "status": "proposed",
    }


def apply_skill_improvement(skill_name: str, version: str) -> Dict[str, Any]:
    """Apply a proposed improvement to a skill.

    Args:
        skill_name: Skill to improve
        version: Version of the improvement to apply

    Returns:
        Dictionary with:
        - skill_name: The skill
        - version: Applied version
        - status: Whether application was successful

    Examples:
        apply_skill_improvement("read_file", "1.1")
    """
    engine = get_improvement_engine()
    profile = engine._load_or_create_profile(skill_name)

    # Find improvement with matching version
    improvement = None
    for imp in profile.improvements:
        if imp.version == version:
            improvement = imp
            break

    if not improvement:
        return {
            "skill_name": skill_name,
            "error": f"Improvement version {version} not found",
        }

    success = engine.apply_improvement(skill_name, improvement)

    return {
        "skill_name": skill_name,
        "version": improvement.version,
        "description": improvement.description,
        "status": "applied" if success else "failed",
    }


def record_skill_execution(
    skill_name: str,
    success: bool,
    latency_ms: float = 0.0,
    context: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Record execution of a skill for performance tracking.

    Args:
        skill_name: Name of the executed skill
        success: Whether execution succeeded
        latency_ms: Execution time in milliseconds
        context: Additional context (e.g., complexity level, data type)

    Returns:
        Dictionary with:
        - skill_name: The skill
        - recorded: Whether execution was recorded
        - total_runs: Total runs of this skill

    Examples:
        record_skill_execution("read_file", True, 45.2, {"file_size": "large"})
        record_skill_execution("web_search", success=True, latency_ms=1200)
    """
    engine = get_improvement_engine()
    engine.record_execution(
        skill_name=skill_name,
        success=success,
        latency_ms=latency_ms,
        context=context or {},
    )

    profile = engine._load_or_create_profile(skill_name)

    return {
        "skill_name": skill_name,
        "recorded": True,
        "total_runs": profile.total_runs,
        "status": "recorded",
    }


def get_improvement_statistics() -> Dict[str, Any]:
    """Get overall improvement statistics.

    Returns:
        Dictionary with global improvement metrics

    Examples:
        get_improvement_statistics()
    """
    engine = get_improvement_engine()
    stats = engine.get_improvement_stats()

    return {
        "total_skills_tracked": stats["total_skills_tracked"],
        "total_improvements_applied": stats["total_improvements_applied"],
        "average_improvement_ratio": round(stats["average_improvement_ratio"], 3),
        "average_confidence": round(stats["avg_confidence"], 2),
        "estimated_total_improvement": f"{(stats['average_improvement_ratio'] - 1.0) * 100:.1f}%",
    }


def get_transfer_opportunities(skill_name: str) -> Dict[str, Any]:
    """Identify skills that could benefit from improvements to another skill.

    Cross-domain transfer learning: find which other skills might benefit
    from successful improvements made to the source skill.

    Args:
        skill_name: Skill with successful improvements

    Returns:
        Dictionary with:
        - source_skill: The source skill
        - candidates: List of skills that could benefit
        - count: Number of candidates

    Examples:
        get_transfer_opportunities("read_file")
    """
    engine = get_improvement_engine()
    candidates = engine.get_transfer_opportunities(skill_name)

    return {
        "source_skill": skill_name,
        "candidates": candidates,
        "count": len(candidates),
        "note": "These skills may benefit from similar improvements to the source skill",
    }


def _get_recommendation(success_rate: float, improvement_potential: float) -> str:
    """Generate actionable recommendation based on performance."""
    if success_rate < 0.7:
        return f"⚠️ Low reliability ({success_rate*100:.0f}%). Recommend reliability improvements."
    elif success_rate < 0.85:
        return f"🔧 Moderate reliability ({success_rate*100:.0f}%). Consider efficiency or generalization improvements."
    elif improvement_potential > 0.15:
        return "📈 Good performance with room for optimization. Consider performance improvements."
    else:
        return "✅ Excellent performance. Monitor for any regression."


# Tool schemas for registry
ANALYZE_PERFORMANCE_SCHEMA = {
    "type": "object",
    "properties": {
        "skill_name": {
            "type": "string",
            "description": "Name of the skill to analyze"
        }
    },
    "required": ["skill_name"]
}

PROPOSE_IMPROVEMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "skill_name": {
            "type": "string",
            "description": "Skill to improve"
        },
        "improvement_type": {
            "type": "string",
            "enum": ["performance", "generalization", "efficiency", "reliability", "maintainability"],
            "description": "Category of improvement"
        },
        "description": {
            "type": "string",
            "description": "Description of the proposed improvement"
        },
        "expected_improvement": {
            "type": "number",
            "description": "Expected improvement ratio (e.g., 1.2 for 20% improvement)",
            "default": 1.1
        }
    },
    "required": ["skill_name"]
}

APPLY_IMPROVEMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "skill_name": {
            "type": "string",
            "description": "Skill to improve"
        },
        "version": {
            "type": "string",
            "description": "Version of the improvement to apply"
        }
    },
    "required": ["skill_name", "version"]
}

RECORD_EXECUTION_SCHEMA = {
    "type": "object",
    "properties": {
        "skill_name": {
            "type": "string",
            "description": "Name of the executed skill"
        },
        "success": {
            "type": "boolean",
            "description": "Whether execution succeeded"
        },
        "latency_ms": {
            "type": "number",
            "description": "Execution time in milliseconds",
            "default": 0.0
        },
        "context": {
            "type": "object",
            "description": "Additional execution context",
            "additionalProperties": {"type": "string"}
        }
    },
    "required": ["skill_name", "success"]
}

TRANSFER_OPPORTUNITIES_SCHEMA = {
    "type": "object",
    "properties": {
        "skill_name": {
            "type": "string",
            "description": "Skill with successful improvements"
        }
    },
    "required": ["skill_name"]
}

# Register tools with the agent
from tools.registry import registry

registry.register(
    name="analyze_skill_performance",
    toolset="learning",
    schema=ANALYZE_PERFORMANCE_SCHEMA,
    handler=lambda args, **kw: analyze_skill_performance(args.get("skill_name", "")),
    check_fn=lambda: True,
    requires_env=None,
    emoji="📊",
    description="Analyze recent performance of a skill"
)

registry.register(
    name="propose_skill_improvement",
    toolset="learning",
    schema=PROPOSE_IMPROVEMENT_SCHEMA,
    handler=lambda args, **kw: propose_skill_improvement(
        skill_name=args.get("skill_name", ""),
        improvement_type=args.get("improvement_type", "performance"),
        description=args.get("description", ""),
        expected_improvement=args.get("expected_improvement", 1.1)
    ),
    check_fn=lambda: True,
    requires_env=None,
    emoji="💡",
    description="Propose an improvement to a skill"
)

registry.register(
    name="apply_skill_improvement",
    toolset="learning",
    schema=APPLY_IMPROVEMENT_SCHEMA,
    handler=lambda args, **kw: apply_skill_improvement(
        skill_name=args.get("skill_name", ""),
        version=args.get("version", "")
    ),
    check_fn=lambda: True,
    requires_env=None,
    emoji="✅",
    description="Apply a proposed improvement to a skill"
)

registry.register(
    name="record_skill_execution",
    toolset="learning",
    schema=RECORD_EXECUTION_SCHEMA,
    handler=lambda args, **kw: record_skill_execution(
        skill_name=args.get("skill_name", ""),
        success=args.get("success", False),
        latency_ms=args.get("latency_ms", 0.0),
        context=args.get("context")
    ),
    check_fn=lambda: True,
    requires_env=None,
    emoji="⏱️",
    description="Record execution of a skill for performance tracking"
)

registry.register(
    name="get_improvement_statistics",
    toolset="learning",
    schema={"type": "object", "properties": {}},
    handler=lambda args, **kw: get_improvement_statistics(),
    check_fn=lambda: True,
    requires_env=None,
    emoji="📈",
    description="Get overall improvement statistics"
)

registry.register(
    name="get_transfer_opportunities",
    toolset="learning",
    schema=TRANSFER_OPPORTUNITIES_SCHEMA,
    handler=lambda args, **kw: get_transfer_opportunities(args.get("skill_name", "")),
    check_fn=lambda: True,
    requires_env=None,
    emoji="🔄",
    description="Identify skills that could benefit from improvements to another skill"
)
