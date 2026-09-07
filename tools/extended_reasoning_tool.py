"""Tools for extended reasoning and decision-making."""

from __future__ import annotations

from typing import Any, Dict, Optional, List

from agent.extended_reasoning import (
    get_reasoning_engine,
    DecisionContext,
    ReasoningComplexity,
)


def analyze_task_complexity(
    task_description: str,
    num_available_tools: int = 0,
    time_budget_seconds: float = 30.0,
) -> Dict[str, Any]:
    """Analyze the complexity of a task to decide reasoning depth.

    Args:
        task_description: Description of the task
        num_available_tools: Number of tools available
        time_budget_seconds: Time available to complete task

    Returns:
        Dictionary with:
        - complexity: SIMPLE, MODERATE, COMPLEX, or CRITICAL
        - reasoning_required: Whether extended reasoning is recommended
        - recommended_approach: Strategy for tackling the task

    Examples:
        analyze_task_complexity("Find the word 'hello' in a text file", 5)
        analyze_task_complexity("Design a secure pentesting workflow for AWS infrastructure")
    """
    engine = get_reasoning_engine()

    complexity = engine.analyze_task_complexity(
        task_description,
        num_available_tools,
        time_budget_seconds,
    )

    return {
        "task_description": task_description,
        "complexity": complexity.value,
        "reasoning_required": complexity != ReasoningComplexity.SIMPLE,
        "recommended_depth": _get_reasoning_depth(complexity),
        "estimated_thinking_tokens": _estimate_thinking_tokens(complexity),
    }


def build_reasoning_chain(
    task_description: str,
    user_intent: str,
    available_tools: List[str],
    time_budget_seconds: float = 30.0,
    safety_constraints: Optional[List[str]] = None,
    domain: str = "general",
) -> Dict[str, Any]:
    """Build a reasoning chain for a complex decision.

    Args:
        task_description: What needs to be done
        user_intent: Why the user wants this done
        available_tools: List of available tools
        time_budget_seconds: Time available for task
        safety_constraints: Security/safety constraints to observe
        domain: Domain context (general, web, file_system, security, data)

    Returns:
        Dictionary with:
        - problem_statement: Clarified problem
        - reasoning_steps: Step-by-step reasoning
        - constraints: Identified constraints
        - alternatives: Alternative approaches considered
        - recommended_tools: Tool sequence to use
        - confidence: Confidence in recommendation

    Examples:
        build_reasoning_chain(
            "Secure a Linux server",
            "Prepare for pentesting assessment",
            ["read_file", "write_file", "web_search"],
            time_budget_seconds=120,
            domain="security"
        )
    """
    engine = get_reasoning_engine()

    complexity = engine.analyze_task_complexity(task_description, len(available_tools), time_budget_seconds)

    context = DecisionContext(
        task_description=task_description,
        user_intent=user_intent,
        available_tools=available_tools,
        time_budget_seconds=time_budget_seconds,
        safety_constraints=safety_constraints or [],
        domain=domain,
        complexity=complexity,
    )

    reasoning = engine.build_reasoning_chain(context)

    return {
        "problem_statement": reasoning.problem_statement,
        "reasoning_steps": reasoning.reasoning_steps,
        "key_constraints": reasoning.key_constraints,
        "alternative_approaches": reasoning.alternative_approaches,
        "recommended_tool_sequence": reasoning.recommended_tool_sequence,
        "confidence_score": reasoning.confidence_score,
        "confidence_level": _get_confidence_label(reasoning.confidence_score),
        "uncertainty_factors": reasoning.uncertainty_factors,
    }


def score_tool_selection(
    task_description: str,
    tool_name: str,
    success_rate: Optional[float] = None,
) -> Dict[str, Any]:
    """Score how well a tool matches a task.

    Args:
        task_description: Description of what needs to be done
        tool_name: Tool to evaluate
        success_rate: Optional recent success rate of the tool

    Returns:
        Dictionary with:
        - tool_name: The tool being evaluated
        - relevance_score: How relevant the tool is (0.0-1.0)
        - confidence: Confidence in the score
        - recommended: Whether to use this tool
        - reasoning: Explanation for the score

    Examples:
        score_tool_selection("Find all Python files", "find_tool", success_rate=0.95)
        score_tool_selection("Analyze web security", "web_search")
    """
    engine = get_reasoning_engine()

    context = {}
    if success_rate is not None:
        context["success_rate"] = success_rate

    result = engine.score_tool_selection(task_description, tool_name, context)

    return result


def plan_tool_sequence(
    task_description: str,
    available_tools: List[str],
    complexity: str = "moderate",
) -> Dict[str, Any]:
    """Plan an optimal sequence of tools for a task.

    Args:
        task_description: What needs to be accomplished
        available_tools: Tools that can be used
        complexity: Task complexity (simple, moderate, complex, critical)

    Returns:
        Dictionary with:
        - tool_sequence: Ordered list of tools to use
        - reasoning: Why this sequence was chosen
        - estimated_time_ms: Rough estimate of execution time
        - fallback_sequence: Alternative sequence if primary fails

    Examples:
        plan_tool_sequence(
            "Parse and validate a large JSON file",
            ["read_file", "json_format_tool", "json_query_tool", "count_file_lines_tool"]
        )
    """
    engine = get_reasoning_engine()

    try:
        complexity_enum = ReasoningComplexity[complexity.upper()]
    except KeyError:
        complexity_enum = ReasoningComplexity.MODERATE

    context = DecisionContext(
        task_description=task_description,
        user_intent="Execute task efficiently",
        available_tools=available_tools,
        time_budget_seconds=60.0,
        complexity=complexity_enum,
    )

    reasoning = engine.build_reasoning_chain(context)

    return {
        "task": task_description,
        "primary_sequence": reasoning.recommended_tool_sequence,
        "reasoning": reasoning.reasoning_steps,
        "confidence": reasoning.confidence_score,
        "fallback_sequence": _generate_fallback(reasoning.recommended_tool_sequence, available_tools),
        "estimated_steps": len(reasoning.recommended_tool_sequence),
    }


def handle_tool_failure(
    original_plan: List[str],
    failed_tool: str,
    failure_reason: str,
    available_tools: List[str],
) -> Dict[str, Any]:
    """Generate fallback strategy when a tool fails.

    Args:
        original_plan: Original tool sequence
        failed_tool: Which tool failed
        failure_reason: Why it failed
        available_tools: Tools available for fallback

    Returns:
        Dictionary with:
        - fallback_sequence: Alternative tool order
        - reasoning: Why this fallback was chosen
        - estimated_recovery_time: Rough estimate to recover

    Examples:
        handle_tool_failure(
            ["web_search", "web_extract"],
            "web_search",
            "API rate limit exceeded",
            ["web_extract", "read_file", "analyze_skill_performance"]
        )
    """
    engine = get_reasoning_engine()

    fallback = engine.generate_fallback_strategy(original_plan, failure_reason, available_tools)

    return {
        "original_sequence": original_plan,
        "failed_tool": failed_tool,
        "failure_reason": failure_reason,
        "fallback_sequence": fallback,
        "changes": _diff_sequences(original_plan, fallback),
        "recommendation": "Use fallback sequence" if fallback != original_plan else "Retry original sequence",
    }


def get_reasoning_insights(
    task_description: str,
    context_clues: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Get reasoning insights for a task without committing to specific tools.

    Args:
        task_description: Description of the task
        context_clues: Optional additional context

    Returns:
        Dictionary with:
        - domain: Inferred domain
        - complexity: Estimated complexity
        - key_questions: Questions to clarify
        - known_obstacles: Potential issues

    Examples:
        get_reasoning_insights(
            "Create a secure configuration for database backups",
            {"environment": "cloud", "database": "PostgreSQL"}
        )
    """
    engine = get_reasoning_engine()

    complexity = engine.analyze_task_complexity(task_description)

    return {
        "task": task_description,
        "complexity": complexity.value,
        "domain": engine._infer_domain(task_description),
        "key_questions": _generate_clarifying_questions(task_description),
        "potential_obstacles": _identify_obstacles(task_description, complexity),
        "reasoning_recommended": complexity != ReasoningComplexity.SIMPLE,
    }


# Helper functions

def _get_reasoning_depth(complexity: ReasoningComplexity) -> str:
    """Get recommended reasoning depth for complexity level."""
    mapping = {
        ReasoningComplexity.SIMPLE: "minimal",
        ReasoningComplexity.MODERATE: "standard",
        ReasoningComplexity.COMPLEX: "deep",
        ReasoningComplexity.CRITICAL: "maximum",
    }
    return mapping.get(complexity, "standard")


def _estimate_thinking_tokens(complexity: ReasoningComplexity) -> int:
    """Estimate token budget for reasoning."""
    mapping = {
        ReasoningComplexity.SIMPLE: 100,
        ReasoningComplexity.MODERATE: 500,
        ReasoningComplexity.COMPLEX: 2000,
        ReasoningComplexity.CRITICAL: 5000,
    }
    return mapping.get(complexity, 500)


def _get_confidence_label(score: float) -> str:
    """Get human-readable confidence label."""
    if score >= 0.9:
        return "certain"
    elif score >= 0.7:
        return "high"
    elif score >= 0.4:
        return "moderate"
    else:
        return "uncertain"


def _generate_fallback(primary: List[str], available: List[str]) -> List[str]:
    """Generate fallback when primary tool sequence is unavailable."""
    # Simple strategy: use available tools in order
    fallback = []
    for tool in primary:
        if tool in available:
            fallback.append(tool)

    # Add other available tools
    for tool in available:
        if tool not in fallback:
            fallback.append(tool)
            if len(fallback) >= 5:  # Limit to 5 tools
                break

    return fallback if fallback else available[:3]


def _diff_sequences(original: List[str], fallback: List[str]) -> List[str]:
    """Identify differences between two tool sequences."""
    removed = [t for t in original if t not in fallback]
    added = [t for t in fallback if t not in original]
    reordered = []

    if removed:
        reordered.append(f"Removed: {', '.join(removed)}")
    if added:
        reordered.append(f"Added: {', '.join(added)}")

    return reordered


def _generate_clarifying_questions(task: str) -> List[str]:
    """Generate questions to clarify task ambiguity."""
    questions = []

    task_lower = task.lower()

    if "file" in task_lower:
        questions.append("What format/encoding should we expect?")
        questions.append("How large might the file be?")

    if "web" in task_lower or "search" in task_lower:
        questions.append("What specific information are we looking for?")
        questions.append("How fresh/current should results be?")

    if "security" in task_lower or "scan" in task_lower:
        questions.append("What are the scope boundaries?")
        questions.append("Are there known vulnerabilities to prioritize?")

    if "analyze" in task_lower or "compare" in task_lower:
        questions.append("What metrics matter most?")
        questions.append("What counts as success?")

    return questions if questions else ["What is the priority/urgency?", "Are there constraints we should know about?"]


def _identify_obstacles(task: str, complexity: ReasoningComplexity) -> List[str]:
    """Identify potential obstacles for a task."""
    obstacles = []

    task_lower = task.lower()

    if "large" in task_lower or "big" in task_lower:
        obstacles.append("Potentially high memory/time requirements")

    if "real-time" in task_lower or "live" in task_lower:
        obstacles.append("May require continuous monitoring/updates")

    if "secure" in task_lower or "encrypt" in task_lower:
        obstacles.append("Security considerations may limit approach")

    if complexity in [ReasoningComplexity.COMPLEX, ReasoningComplexity.CRITICAL]:
        obstacles.append("Task complexity may require iterative refinement")
        obstacles.append("May encounter unexpected edge cases")

    return obstacles if obstacles else ["Unknown unknowns from task specification"]


# Tool schemas for registry
ANALYZE_COMPLEXITY_SCHEMA = {
    "type": "object",
    "properties": {
        "task_description": {
            "type": "string",
            "description": "Description of the task to analyze"
        },
        "num_available_tools": {
            "type": "integer",
            "description": "Number of tools available",
            "default": 0
        },
        "time_budget_seconds": {
            "type": "number",
            "description": "Time budget in seconds",
            "default": 30.0
        }
    },
    "required": ["task_description"]
}

BUILD_REASONING_SCHEMA = {
    "type": "object",
    "properties": {
        "task_description": {
            "type": "string",
            "description": "What needs to be done"
        },
        "user_intent": {
            "type": "string",
            "description": "Why the user wants this done"
        },
        "available_tools": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of available tools"
        },
        "time_budget_seconds": {
            "type": "number",
            "description": "Time budget in seconds",
            "default": 30.0
        },
        "domain": {
            "type": "string",
            "enum": ["general", "web", "file_system", "security", "data"],
            "description": "Domain context",
            "default": "general"
        }
    },
    "required": ["task_description", "user_intent", "available_tools"]
}

SCORE_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "task_description": {
            "type": "string",
            "description": "Description of the task"
        },
        "tool_name": {
            "type": "string",
            "description": "Name of the tool to evaluate"
        },
        "success_rate": {
            "type": "number",
            "description": "Recent success rate of the tool (0.0-1.0)",
            "minimum": 0.0,
            "maximum": 1.0
        }
    },
    "required": ["task_description", "tool_name"]
}

PLAN_SEQUENCE_SCHEMA = {
    "type": "object",
    "properties": {
        "task_description": {
            "type": "string",
            "description": "What needs to be accomplished"
        },
        "available_tools": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Tools that can be used"
        },
        "complexity": {
            "type": "string",
            "enum": ["simple", "moderate", "complex", "critical"],
            "description": "Estimated task complexity",
            "default": "moderate"
        }
    },
    "required": ["task_description", "available_tools"]
}

HANDLE_FAILURE_SCHEMA = {
    "type": "object",
    "properties": {
        "original_plan": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Original tool sequence"
        },
        "failed_tool": {
            "type": "string",
            "description": "Which tool failed"
        },
        "failure_reason": {
            "type": "string",
            "description": "Why it failed"
        },
        "available_tools": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Tools still available"
        }
    },
    "required": ["original_plan", "failed_tool", "failure_reason", "available_tools"]
}

# Register tools
from tools.registry import registry

registry.register(
    name="analyze_task_complexity",
    toolset="reasoning",
    schema=ANALYZE_COMPLEXITY_SCHEMA,
    handler=lambda args, **kw: analyze_task_complexity(
        args.get("task_description", ""),
        args.get("num_available_tools", 0),
        args.get("time_budget_seconds", 30.0)
    ),
    check_fn=lambda: True,
    requires_env=None,
    emoji="🎯",
    description="Analyze task complexity to determine reasoning depth"
)

registry.register(
    name="build_reasoning_chain",
    toolset="reasoning",
    schema=BUILD_REASONING_SCHEMA,
    handler=lambda args, **kw: build_reasoning_chain(
        args.get("task_description", ""),
        args.get("user_intent", ""),
        args.get("available_tools", []),
        args.get("time_budget_seconds", 30.0),
        args.get("safety_constraints"),
        args.get("domain", "general")
    ),
    check_fn=lambda: True,
    requires_env=None,
    emoji="🧠",
    description="Build structured reasoning chain for complex decisions"
)

registry.register(
    name="score_tool_selection",
    toolset="reasoning",
    schema=SCORE_TOOL_SCHEMA,
    handler=lambda args, **kw: score_tool_selection(
        args.get("task_description", ""),
        args.get("tool_name", ""),
        args.get("success_rate")
    ),
    check_fn=lambda: True,
    requires_env=None,
    emoji="⚖️",
    description="Score how well a tool matches a task"
)

registry.register(
    name="plan_tool_sequence",
    toolset="reasoning",
    schema=PLAN_SEQUENCE_SCHEMA,
    handler=lambda args, **kw: plan_tool_sequence(
        args.get("task_description", ""),
        args.get("available_tools", []),
        args.get("complexity", "moderate")
    ),
    check_fn=lambda: True,
    requires_env=None,
    emoji="🔗",
    description="Plan optimal sequence of tools for a task"
)

registry.register(
    name="handle_tool_failure",
    toolset="reasoning",
    schema=HANDLE_FAILURE_SCHEMA,
    handler=lambda args, **kw: handle_tool_failure(
        args.get("original_plan", []),
        args.get("failed_tool", ""),
        args.get("failure_reason", ""),
        args.get("available_tools", [])
    ),
    check_fn=lambda: True,
    requires_env=None,
    emoji="🔄",
    description="Generate fallback strategy when tool fails"
)

registry.register(
    name="get_reasoning_insights",
    toolset="reasoning",
    schema={
        "type": "object",
        "properties": {
            "task_description": {
                "type": "string",
                "description": "Description of the task"
            },
            "context_clues": {
                "type": "object",
                "description": "Optional additional context",
                "additionalProperties": {"type": "string"}
            }
        },
        "required": ["task_description"]
    },
    handler=lambda args, **kw: get_reasoning_insights(
        args.get("task_description", ""),
        args.get("context_clues")
    ),
    check_fn=lambda: True,
    requires_env=None,
    emoji="💡",
    description="Get reasoning insights without committing to tools"
)
