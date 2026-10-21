"""Agent capabilities registry and discovery system.

Enables agents to:
- Discover available tools and capabilities
- Learn from execution history
- Adapt strategy based on past success
- Build capability profiles
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Set
from enum import Enum


class CapabilityType(Enum):
    """Types of agent capabilities."""
    CODE_UNDERSTANDING = "code_understanding"
    PLANNING = "planning"
    EXECUTION = "execution"
    DEBUGGING = "debugging"
    OPTIMIZATION = "optimization"
    TESTING = "testing"
    DOCUMENTATION = "documentation"


@dataclass
class Capability:
    """Single agent capability."""
    name: str
    type: CapabilityType
    description: str
    success_rate: float = 0.0
    usage_count: int = 0
    avg_latency_ms: float = 0.0
    associated_tools: List[str] = field(default_factory=list)
    best_for: List[str] = field(default_factory=list)


class CapabilitiesRegistry:
    """Registry of agent capabilities and learning."""

    def __init__(self):
        self.capabilities: Dict[str, Capability] = {}
        self.task_history: List[Dict[str, Any]] = []
        self.learned_patterns: Dict[str, List[str]] = {}

    def register_capability(self, capability: Capability):
        """Register a new capability."""
        self.capabilities[capability.name] = capability

    def record_task(
        self,
        task_description: str,
        capabilities_used: List[str],
        success: bool,
        latency_ms: float,
        insights: str = "",
    ):
        """Record task execution."""
        record = {
            "task": task_description,
            "capabilities": capabilities_used,
            "success": success,
            "latency_ms": latency_ms,
            "insights": insights,
        }
        self.task_history.append(record)

        # Update capability stats
        for cap_name in capabilities_used:
            if cap_name in self.capabilities:
                cap = self.capabilities[cap_name]
                total = cap.usage_count + 1
                prev_success_count = cap.success_rate * cap.usage_count
                new_success_count = prev_success_count + (1 if success else 0)

                cap.usage_count = total
                cap.success_rate = new_success_count / total
                cap.avg_latency_ms = (
                    (cap.avg_latency_ms * (total - 1) + latency_ms) / total
                )

    def get_best_capabilities_for(self, task_description: str) -> List[Capability]:
        """Get best capabilities for a task."""
        # Simple matching - could be more sophisticated
        relevant = []
        desc_lower = task_description.lower()

        for cap in self.capabilities.values():
            if any(
                keyword in desc_lower
                for keyword in cap.best_for + [cap.name.lower().replace("_", " ")]
            ):
                relevant.append(cap)

        # Sort by success rate
        relevant.sort(key=lambda c: c.success_rate, reverse=True)
        return relevant

    def get_capability_profile(self) -> Dict[str, Any]:
        """Get comprehensive capability profile."""
        total_tasks = len(self.task_history)
        successful_tasks = sum(1 for t in self.task_history if t["success"])

        return {
            "total_tasks_executed": total_tasks,
            "success_rate": successful_tasks / total_tasks if total_tasks else 0,
            "capabilities": {
                name: {
                    "type": cap.type.value,
                    "success_rate": cap.success_rate,
                    "usage_count": cap.usage_count,
                    "avg_latency_ms": cap.avg_latency_ms,
                }
                for name, cap in self.capabilities.items()
            },
            "strongest_capabilities": [
                name for name, cap in sorted(
                    self.capabilities.items(),
                    key=lambda x: x[1].success_rate,
                    reverse=True,
                )[:5]
            ],
        }

    def suggest_capability_improvement(self) -> List[str]:
        """Suggest capabilities to improve."""
        suggestions = []

        for name, cap in self.capabilities.items():
            if cap.success_rate < 0.7 and cap.usage_count > 5:
                suggestions.append(
                    f"Improve {name}: success rate {cap.success_rate:.1%}"
                )

        return suggestions


__all__ = ["CapabilitiesRegistry", "Capability", "CapabilityType"]
