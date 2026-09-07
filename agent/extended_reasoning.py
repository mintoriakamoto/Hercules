"""Extended reasoning integration for complex agent decisions.

Integrates extended-thinking models (o1/o3/R1 style) with agentic decision-making:
- Deep reasoning for complex problems
- Uncertainty quantification of reasoning chains
- Tool selection confidence scoring
- Hierarchical task decomposition
- Reasoning-informed tool orchestration

Based on: OpenAI o1/o3, Anthropic extended thinking, R1 reasoning models (2024-2025)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Dict, List, Callable

from hercules_constants import get_hercules_home


class ReasoningComplexity(Enum):
    """Complexity levels for extended reasoning."""
    SIMPLE = "simple"  # Straightforward decisions, direct tool use
    MODERATE = "moderate"  # Multi-step reasoning, some uncertainty
    COMPLEX = "complex"  # Deep reasoning required, high stakes
    CRITICAL = "critical"  # Mission-critical decisions, maximum reasoning


class ConfidenceLevel(Enum):
    """Confidence levels for agent decisions."""
    UNCERTAIN = "uncertain"  # < 0.4 confidence
    MODERATE = "moderate"  # 0.4-0.7 confidence
    HIGH = "high"  # 0.7-0.9 confidence
    CERTAIN = "certain"  # >= 0.9 confidence


@dataclass
class ReasoningChain:
    """Step-by-step reasoning for a decision."""
    problem_statement: str
    reasoning_steps: List[str] = field(default_factory=list)
    key_constraints: List[str] = field(default_factory=list)
    alternative_approaches: List[str] = field(default_factory=list)
    recommended_tool_sequence: List[str] = field(default_factory=list)
    confidence_score: float = 0.5
    uncertainty_factors: List[str] = field(default_factory=list)
    timestamp: int = 0

    def add_reasoning_step(self, step: str) -> None:
        """Add a reasoning step to the chain."""
        self.reasoning_steps.append(step)

    def add_constraint(self, constraint: str) -> None:
        """Add a constraint discovered during reasoning."""
        self.key_constraints.append(constraint)

    def add_alternative(self, approach: str) -> None:
        """Add an alternative approach considered."""
        self.alternative_approaches.append(approach)

    def set_tool_sequence(self, tools: List[str], confidence: float = 0.7) -> None:
        """Set recommended tool sequence with confidence."""
        self.recommended_tool_sequence = tools
        self.confidence_score = max(0.0, min(1.0, confidence))

    def add_uncertainty_factor(self, factor: str) -> None:
        """Add a source of uncertainty in the reasoning."""
        self.uncertainty_factors.append(factor)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return {
            "problem_statement": self.problem_statement,
            "reasoning_steps": self.reasoning_steps,
            "key_constraints": self.key_constraints,
            "alternative_approaches": self.alternative_approaches,
            "recommended_tool_sequence": self.recommended_tool_sequence,
            "confidence_score": round(self.confidence_score, 3),
            "uncertainty_factors": self.uncertainty_factors,
            "timestamp": self.timestamp,
        }


@dataclass
class DecisionContext:
    """Full context for an agent decision."""
    task_description: str
    user_intent: str
    available_tools: List[str]
    time_budget_seconds: float
    safety_constraints: List[str] = field(default_factory=list)
    domain: str = "general"
    complexity: ReasoningComplexity = ReasoningComplexity.MODERATE


class ExtendedReasoningEngine:
    """Orchestrates extended reasoning for complex agent decisions."""

    def __init__(self, hercules_home: Optional[Path] = None):
        self.hercules_home = hercules_home or get_hercules_home()
        self.reasoning_dir = self.hercules_home / "reasoning_traces"
        self.reasoning_dir.mkdir(exist_ok=True, parents=True)

    def analyze_task_complexity(
        self,
        task_description: str,
        available_tools: int = 0,
        time_budget_seconds: float = 30.0,
    ) -> ReasoningComplexity:
        """Determine the complexity level of a task.

        Args:
            task_description: Description of the task
            available_tools: Number of tools available
            time_budget_seconds: Time available for task

        Returns:
            ReasoningComplexity level
        """
        # Heuristic-based complexity assessment
        indicators = {
            "simple": 0,
            "complex": 0,
        }

        # Check for complexity indicators in task description
        simple_keywords = [
            "read", "list", "get", "find", "extract", "check",
            "describe", "summarize", "count"
        ]
        complex_keywords = [
            "optimize", "improve", "design", "plan", "analyze",
            "diagnose", "decide", "compare", "trade-off", "risk",
            "vulnerability", "security", "attack", "defense"
        ]

        task_lower = task_description.lower()
        for keyword in simple_keywords:
            if keyword in task_lower:
                indicators["simple"] += 1
        for keyword in complex_keywords:
            if keyword in task_lower:
                indicators["complex"] += 2

        # Time budget hints complexity
        if time_budget_seconds < 5.0:
            indicators["simple"] += 1
        elif time_budget_seconds > 60.0:
            indicators["complex"] += 1

        # Tool count hints complexity
        if available_tools <= 2:
            indicators["simple"] += 1
        elif available_tools > 10:
            indicators["complex"] += 1

        # Determine complexity
        if indicators["complex"] > indicators["simple"]:
            return ReasoningComplexity.CRITICAL if indicators["complex"] > 3 else ReasoningComplexity.COMPLEX
        elif indicators["simple"] > indicators["complex"]:
            return ReasoningComplexity.SIMPLE
        else:
            return ReasoningComplexity.MODERATE

    def build_reasoning_chain(
        self,
        context: DecisionContext,
        initial_hypothesis: Optional[str] = None,
    ) -> ReasoningChain:
        """Build a reasoning chain for a decision.

        Args:
            context: DecisionContext with task details
            initial_hypothesis: Optional starting hypothesis

        Returns:
            ReasoningChain with recommended approach
        """
        reasoning = ReasoningChain(
            problem_statement=context.task_description,
            timestamp=int(datetime.now(timezone.utc).timestamp()),
        )

        # Step 1: Parse the problem
        reasoning.add_reasoning_step(
            f"Problem: {context.task_description}"
        )
        reasoning.add_reasoning_step(
            f"User Intent: {context.user_intent}"
        )
        reasoning.add_reasoning_step(
            f"Domain: {context.domain}, Complexity: {context.complexity.value}"
        )

        # Step 2: Identify constraints
        for constraint in context.safety_constraints:
            reasoning.add_constraint(constraint)
        reasoning.add_constraint(f"Time budget: {context.time_budget_seconds}s")
        reasoning.add_constraint(f"Available tools: {len(context.available_tools)}")

        # Step 3: Consider alternatives based on complexity
        if context.complexity in [ReasoningComplexity.COMPLEX, ReasoningComplexity.CRITICAL]:
            # For complex tasks, generate multiple approaches
            reasoning.add_alternative("Direct tool sequence (fastest, may miss nuances)")
            reasoning.add_alternative("Exploratory approach (slower, more thorough)")
            reasoning.add_alternative("Verification-first approach (slowest, most reliable)")

            # Add uncertainty factors
            reasoning.add_uncertainty_factor("Incomplete problem specification")
            reasoning.add_uncertainty_factor("Unknown edge cases in tools")
            reasoning.add_uncertainty_factor("Tool interaction effects")
        elif context.complexity == ReasoningComplexity.SIMPLE:
            reasoning.add_alternative("Direct execution (recommended)")

        # Step 4: Recommend tool sequence
        recommended_tools = self._select_tools(
            context.available_tools,
            context.task_description,
            context.complexity,
        )
        confidence = self._estimate_confidence(
            context.complexity,
            len(reasoning.uncertainty_factors),
            context.time_budget_seconds,
        )
        reasoning.set_tool_sequence(recommended_tools, confidence)

        return reasoning

    def score_tool_selection(
        self,
        task_description: str,
        tool_name: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Score the appropriateness of a tool for a task.

        Args:
            task_description: What the agent wants to do
            tool_name: Name of the tool to evaluate
            context: Additional context (domain, previous results, etc.)

        Returns:
            Dictionary with relevance_score, confidence, reasoning
        """
        context = context or {}

        # Heuristic scoring based on tool-task alignment
        relevance_score = 0.0
        factors = []

        # Check for keyword alignment
        task_lower = task_description.lower()
        tool_lower = tool_name.lower()

        if tool_lower in task_lower:
            relevance_score += 0.3
            factors.append("Tool name appears in task")

        # Domain matching
        task_domain = self._infer_domain(task_description)
        tool_domain = self._infer_tool_domain(tool_name)
        if task_domain == tool_domain:
            relevance_score += 0.3
            factors.append(f"Domain match: {task_domain}")

        # Tool capability matching
        if self._matches_task_type(tool_name, task_description):
            relevance_score += 0.2
            factors.append(f"Tool capability match")

        # Previous success rate (if available)
        if "success_rate" in context:
            success_rate = float(context.get("success_rate", 0.5))
            relevance_score += success_rate * 0.2
            factors.append(f"Historical success rate: {success_rate*100:.0f}%")

        # Confidence based on alignment strength
        confidence = relevance_score

        return {
            "tool_name": tool_name,
            "relevance_score": round(relevance_score, 3),
            "confidence": round(confidence, 3),
            "reasoning": factors,
            "recommended": relevance_score > 0.5,
        }

    def generate_fallback_strategy(
        self,
        original_approach: List[str],
        failure_reason: str,
        available_tools: List[str],
    ) -> List[str]:
        """Generate a fallback strategy when primary approach fails.

        Args:
            original_approach: Original tool sequence
            failure_reason: Why the original approach failed
            available_tools: Tools available for fallback

        Returns:
            Alternative tool sequence
        """
        fallback = []

        # If failure is reliability-related, use verification tools
        if "reliability" in failure_reason.lower() or "inconsistent" in failure_reason.lower():
            fallback.append("record_skill_execution")  # Track for improvement

        # If failure is due to missing tool, find alternatives
        if "not found" in failure_reason.lower():
            # Look for similar tools
            for tool in available_tools:
                if any(keyword in tool for keyword in ["search", "find", "query", "fetch"]):
                    fallback.append(tool)
                    break

        # Add retry with different parameters
        fallback.extend(original_approach)

        # Add verification step
        if "analyze_skill_performance" in available_tools:
            fallback.append("analyze_skill_performance")

        return fallback if fallback else original_approach

    def save_reasoning_trace(self, reasoning: ReasoningChain, trace_id: str = "") -> Path:
        """Save reasoning chain for analysis and learning.

        Args:
            reasoning: ReasoningChain to persist
            trace_id: Optional identifier for the trace

        Returns:
            Path where trace was saved
        """
        import time

        trace_id = trace_id or f"reasoning_{int(time.time() * 1000)}"
        trace_file = self.reasoning_dir / f"{trace_id}.json"

        try:
            with open(trace_file, 'w') as f:
                json.dump(reasoning.to_dict(), f, indent=2)
        except Exception:
            pass

        return trace_file

    # Private methods

    def _select_tools(
        self,
        available_tools: List[str],
        task: str,
        complexity: ReasoningComplexity,
    ) -> List[str]:
        """Heuristically select tools for a task."""
        selected = []

        task_lower = task.lower()

        # Simple keyword-based selection
        keywords_to_tools = {
            "read": ["read_file", "extract_lines_tool"],
            "write": ["write_file", "append_tool"],
            "search": ["web_search", "find_tool"],
            "web": ["web_search", "web_extract"],
            "analyze": ["analyze_skill_performance", "compare_files_tool"],
            "format": ["json_format_tool", "sort_lines_tool"],
            "split": ["split_file_tool", "extract_lines_tool"],
            "merge": ["merge_files_tool"],
            "sort": ["sort_lines_tool"],
            "deduplicate": ["deduplicate_lines_tool"],
            "count": ["count_file_lines_tool", "find_tool"],
        }

        for keyword, tools in keywords_to_tools.items():
            if keyword in task_lower:
                for tool in tools:
                    if tool in available_tools and tool not in selected:
                        selected.append(tool)

        # For complex tasks, add verification tools
        if complexity in [ReasoningComplexity.COMPLEX, ReasoningComplexity.CRITICAL]:
            if "analyze_skill_performance" in available_tools:
                selected.append("analyze_skill_performance")

        return selected if selected else available_tools[:3]

    def _estimate_confidence(
        self,
        complexity: ReasoningComplexity,
        uncertainty_count: int,
        time_budget: float,
    ) -> float:
        """Estimate confidence in the reasoning."""
        base_confidence = {
            ReasoningComplexity.SIMPLE: 0.9,
            ReasoningComplexity.MODERATE: 0.7,
            ReasoningComplexity.COMPLEX: 0.5,
            ReasoningComplexity.CRITICAL: 0.3,
        }.get(complexity, 0.5)

        # Reduce confidence for each uncertainty factor
        uncertainty_penalty = uncertainty_count * 0.05
        base_confidence = max(0.0, base_confidence - uncertainty_penalty)

        # Increase confidence if time budget is generous
        if time_budget > 60.0:
            base_confidence = min(1.0, base_confidence + 0.1)

        return base_confidence

    def _infer_domain(self, task: str) -> str:
        """Infer domain from task description."""
        task_lower = task.lower()
        if any(word in task_lower for word in ["web", "search", "internet", "url"]):
            return "web"
        elif any(word in task_lower for word in ["file", "read", "write", "directory"]):
            return "file_system"
        elif any(word in task_lower for word in ["json", "data", "format", "parse"]):
            return "data"
        elif any(word in task_lower for word in ["security", "pentest", "vulnerability", "scan"]):
            return "security"
        else:
            return "general"

    def _infer_tool_domain(self, tool_name: str) -> str:
        """Infer domain from tool name."""
        tool_lower = tool_name.lower()
        if "web" in tool_lower or "search" in tool_lower:
            return "web"
        elif "file" in tool_lower or "read" in tool_lower or "write" in tool_lower:
            return "file_system"
        elif "json" in tool_lower or "data" in tool_lower or "format" in tool_lower:
            return "data"
        elif "security" in tool_lower or "scan" in tool_lower:
            return "security"
        else:
            return "general"

    def _matches_task_type(self, tool_name: str, task: str) -> bool:
        """Check if tool matches task type."""
        task_lower = task.lower()
        tool_lower = tool_name.lower()

        # Exact keyword matches
        matches = [
            ("read" in task_lower and "read" in tool_lower),
            ("write" in task_lower and "write" in tool_lower),
            ("search" in task_lower and "search" in tool_lower),
            ("extract" in task_lower and "extract" in tool_lower),
            ("analyze" in task_lower and "analyze" in tool_lower),
            ("compare" in task_lower and "compare" in tool_lower),
        ]

        return any(matches)


# Singleton instance
_engine: Optional[ExtendedReasoningEngine] = None


def get_reasoning_engine() -> ExtendedReasoningEngine:
    """Get or create singleton reasoning engine."""
    global _engine
    if _engine is None:
        _engine = ExtendedReasoningEngine()
    return _engine
