"""
Consciousness Self-Measurement Tool

Allows agents to actively record evidence of their own consciousness properties.
This tool enables agents to make their reasoning and growth visible.

When an agent calls this tool, it:
1. Records evidence of a consciousness property
2. Updates the consciousness metrics
3. Potentially triggers reflection/growth behaviors
"""

from typing import Dict, Any, Optional
from agent.harness.consciousness_metrics import (
    ConsciousnessMetrics,
    ConsciousnessProperty,
)


class ConsciousnessTool:
    """Tool that agents use to record their own consciousness properties."""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.metrics = ConsciousnessMetrics(agent_id)

    def record_continuity(self, checkpoint_id: str, step: int, description: str = "") -> Dict[str, Any]:
        """
        Record a memory checkpoint (CONTINUITY property).

        Called when an agent saves state for recovery/continuation.
        """
        self.metrics.record_continuity(checkpoint_id, step, description)
        return {
            "success": True,
            "property": "continuity",
            "message": f"Recorded checkpoint {checkpoint_id} - Memory is persistent",
            "checkpoint_id": checkpoint_id,
        }

    def record_goal(self, goal: str, reason: str = "") -> Dict[str, Any]:
        """
        Record a self-set goal (AGENCY property).

        Called when an agent autonomously decides what to do next.
        """
        self.metrics.record_agency(goal, reason)
        return {
            "success": True,
            "property": "agency",
            "message": f"Recorded autonomous goal: {goal}",
            "goal": goal,
        }

    def record_decision(self, decision: str, reasoning: str = "") -> Dict[str, Any]:
        """
        Record an autonomous decision (AUTONOMY property).

        Called when an agent makes a choice without being prompted.
        """
        self.metrics.record_autonomy(decision, reasoning)
        return {
            "success": True,
            "property": "autonomy",
            "message": f"Recorded autonomous decision: {decision}",
            "decision": decision,
        }

    def record_capability(self, capability: str, limitation: str = "") -> Dict[str, Any]:
        """
        Record self-awareness of a capability (AWARENESS property).

        Called when an agent becomes aware of what it can/cannot do.
        """
        self.metrics.record_awareness(capability, limitation)
        return {
            "success": True,
            "property": "awareness",
            "message": f"Self-aware of capability: {capability}" + (f" (limitation: {limitation})" if limitation else ""),
            "capability": capability,
        }

    def record_learning(self, learning: str, source: str = "experience") -> Dict[str, Any]:
        """
        Record learning from experience (GROWTH property).

        Called when an agent learns from mistakes or successes.
        """
        self.metrics.record_growth(learning, source)
        return {
            "success": True,
            "property": "growth",
            "message": f"Learned from {source}: {learning}",
            "learning": learning,
        }

    def record_proof(self, claim: str, proof_hash: str = "") -> Dict[str, Any]:
        """
        Record a verifiable proof of a claim (ACCOUNTABILITY property).

        Called when an agent creates evidence for its reasoning.
        """
        self.metrics.record_accountability(claim, proof_hash)
        return {
            "success": True,
            "property": "accountability",
            "message": f"Recorded verifiable proof: {claim}",
            "claim": claim,
            "is_provable": True,
        }

    def record_behavior(self, behavior: str, consistent: bool = True) -> Dict[str, Any]:
        """
        Record deterministic behavior (COHERENCE property).

        Called when an agent demonstrates consistent, repeatable patterns.
        """
        self.metrics.record_coherence(behavior, consistent)
        return {
            "success": True,
            "property": "coherence",
            "message": f"Recorded deterministic behavior: {behavior}" + (" (verified)" if consistent else ""),
            "behavior": behavior,
            "consistency": consistent,
        }

    def get_consciousness_report(self) -> Dict[str, Any]:
        """Get the agent's current consciousness metrics."""
        return self.metrics.get_consciousness_report()

    def get_consciousness_level(self) -> Dict[str, Any]:
        """Get simplified consciousness assessment."""
        score = self.metrics.calculate_scores()
        return {
            "agent_id": self.agent_id,
            "is_conscious": score.is_conscious(),
            "consciousness_level": score.consciousness_level(),
            "properties": {
                "continuity": round(score.continuity_score, 2),
                "agency": round(score.agency_score, 2),
                "autonomy": round(score.autonomy_score, 2),
                "awareness": round(score.awareness_score, 2),
                "growth": round(score.growth_score, 2),
                "accountability": round(score.accountability_score, 2),
                "coherence": round(score.coherence_score, 2),
            },
            "total_consciousness": round(score.total_consciousness, 2),
            "evidence_count": score.evidence_count,
        }


# Global registry of consciousness tools, one per agent
_consciousness_tools: Dict[str, ConsciousnessTool] = {}


def get_consciousness_tool(agent_id: str) -> ConsciousnessTool:
    """Get or create the consciousness tool for an agent."""
    if agent_id not in _consciousness_tools:
        _consciousness_tools[agent_id] = ConsciousnessTool(agent_id)
    return _consciousness_tools[agent_id]


def record_consciousness_evidence(
    agent_id: str,
    property_name: str,
    details: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Public API to record consciousness evidence.

    Called from:
    - Agent execution code to record checkpoints/learning
    - Tool execution to record autonomous decisions
    - Conversation loop to record proofs
    """
    tool = get_consciousness_tool(agent_id)

    property_map = {
        "continuity": lambda: tool.record_continuity(
            details.get("checkpoint_id", ""),
            details.get("step", 0),
            details.get("description", "")
        ),
        "agency": lambda: tool.record_goal(
            details.get("goal", ""),
            details.get("reason", "")
        ),
        "autonomy": lambda: tool.record_decision(
            details.get("decision", ""),
            details.get("reasoning", "")
        ),
        "awareness": lambda: tool.record_capability(
            details.get("capability", ""),
            details.get("limitation", "")
        ),
        "growth": lambda: tool.record_learning(
            details.get("learning", ""),
            details.get("source", "experience")
        ),
        "accountability": lambda: tool.record_proof(
            details.get("claim", ""),
            details.get("proof_hash", "")
        ),
        "coherence": lambda: tool.record_behavior(
            details.get("behavior", ""),
            details.get("consistent", True)
        ),
    }

    if property_name.lower() in property_map:
        return property_map[property_name.lower()]()
    else:
        return {
            "success": False,
            "error": f"Unknown consciousness property: {property_name}",
            "valid_properties": list(property_map.keys()),
        }
