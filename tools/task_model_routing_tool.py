"""Tool for task-aware model routing in agent delegation.

Allows agents to query which model is most appropriate for a given task,
enabling cost-aware and capability-aware delegation.
"""

import logging
from typing import Any, Dict

from agent.task_aware_model_router import (
    ModelTier,
    get_model_router,
    route_task_to_model,
)

logger = logging.getLogger(__name__)


def analyze_task_model_routing(args: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze a task and recommend the most appropriate model.

    This tool helps agents make cost-aware and capability-aware decisions
    when delegating work or choosing models for subtasks.

    Args:
        args: dict with keys:
            - task_description (str): Description of the task (required)
            - available_tools (int): Number of tools available (optional, default 0)
            - include_reasoning (bool): Include reasoning explanation (optional,
              default true)

    Returns:
        dict with:
            - recommended_model: Recommended model ID
            - recommended_tier: Tier (fast_cheap, balanced, capable, extended)
            - complexity: Detected task complexity level
            - category: Detected task category (if any)
            - confidence: Confidence score (0-1)
            - cost_savings_estimate: Estimated cost savings percentage
            - reasoning: Detailed explanation of the recommendation
    """
    task_description = args.get("task_description", "").strip()
    if not task_description:
        return {
            "error": "task_description is required",
            "recommended_model": None,
            "recommended_tier": ModelTier.BALANCED.value,
        }

    available_tools = args.get("available_tools", 0)
    try:
        available_tools = int(available_tools)
    except (ValueError, TypeError):
        available_tools = 0

    include_reasoning = args.get("include_reasoning", True)

    try:
        model, decision = route_task_to_model(task_description, available_tools)

        result = {
            "recommended_model": model,
            "recommended_tier": decision.recommended_tier.value,
            "complexity": decision.complexity.value,
            "category": decision.category.value if decision.category else None,
            "confidence": round(decision.confidence, 3),
            "cost_savings_estimate": (
                round(decision.cost_savings_estimate, 1)
                if decision.cost_savings_estimate is not None
                else None
            ),
        }

        if include_reasoning:
            result["reasoning"] = decision.reasoning

        logger.info(
            "Task routing analysis: %s -> %s (%s tier, %.2f confidence)",
            task_description[:60],
            model,
            decision.recommended_tier.value,
            decision.confidence,
        )

        return result

    except Exception as e:
        logger.exception("Error analyzing task for model routing: %s", e)
        return {
            "error": f"Failed to analyze task: {str(e)}",
            "recommended_model": "claude-sonnet-5",  # Safe fallback
            "recommended_tier": ModelTier.BALANCED.value,
        }


def get_model_tier_info(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get information about available model tiers and their characteristics.

    Returns:
        dict with:
            - tiers: List of available tiers with their models
            - tier_characteristics: Description of each tier's characteristics
    """
    router = get_model_router()

    tiers = {}
    for tier, models in router.model_tier_mapping.items():
        tiers[tier.value] = models

    tier_characteristics = {
        ModelTier.FAST_CHEAP.value: {
            "use_for": "Simple tasks, information retrieval, fast response required",
            "examples": ["List files", "Read configuration", "Extract text"],
            "cost_level": "Low",
            "speed_level": "Fast",
        },
        ModelTier.BALANCED.value: {
            "use_for": "General-purpose tasks, analysis, moderate reasoning",
            "examples": ["Analyze data", "Write documentation", "Debug code"],
            "cost_level": "Medium",
            "speed_level": "Moderate",
        },
        ModelTier.CAPABLE.value: {
            "use_for": "Complex reasoning, system design, security analysis",
            "examples": [
                "Design architecture",
                "Perform security review",
                "Complex optimization",
            ],
            "cost_level": "High",
            "speed_level": "Moderate",
        },
        ModelTier.EXTENDED.value: {
            "use_for": "Deep research, extended reasoning, comprehensive analysis",
            "examples": [
                "Research paper review",
                "Comprehensive audit",
                "Novel problem solving",
            ],
            "cost_level": "Very High",
            "speed_level": "Slow",
        },
    }

    return {
        "available_tiers": list(tiers.keys()),
        "tier_models": tiers,
        "tier_characteristics": tier_characteristics,
    }


# Tool registration
_TASK_MODEL_ROUTING_TOOL = {
    "name": "task_model_routing",
    "handler": analyze_task_model_routing,
    "description": (
        "Analyze a task and recommend the most appropriate model based on complexity, "
        "cost, and capability requirements. Use this to make cost-aware decisions when "
        "delegating work or choosing models for subtasks."
    ),
    "args": {
        "task_description": {
            "type": "string",
            "description": (
                "Description of the task to analyze. "
                "Should be specific enough to determine complexity and requirements."
            ),
        },
        "available_tools": {
            "type": "integer",
            "description": (
                "Number of tools available to the agent performing this task. "
                "More tools may enable cheaper models. Optional, defaults to 0."
            ),
        },
        "include_reasoning": {
            "type": "boolean",
            "description": (
                "Include detailed reasoning explaining the recommendation. "
                "Optional, defaults to true."
            ),
        },
    },
}

_GET_TIER_INFO_TOOL = {
    "name": "get_model_tier_info",
    "handler": get_model_tier_info,
    "description": (
        "Get information about available model tiers, their characteristics, "
        "and which models are in each tier. Use this to understand the model "
        "routing landscape and make informed decisions."
    ),
    "args": {},
}


def get_tools() -> list:
    """Return list of tools provided by this module."""
    return [_TASK_MODEL_ROUTING_TOOL, _GET_TIER_INFO_TOOL]


if __name__ == "__main__":
    # Test the tools
    print("Testing task_model_routing tool...")
    result = analyze_task_model_routing(
        {
            "task_description": "Analyze the security of our AWS infrastructure",
            "available_tools": 10,
            "include_reasoning": True,
        }
    )
    print(f"Result: {result}\n")

    print("Testing get_model_tier_info tool...")
    tier_info = get_model_tier_info({})
    print(f"Tiers: {tier_info['available_tiers']}")
    print(f"Characteristics: {list(tier_info['tier_characteristics'].keys())}")
