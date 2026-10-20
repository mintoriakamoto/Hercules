"""Task complexity classification for intelligent model routing.

Analyzes request characteristics to determine optimal model tier:
- SIMPLE (0-30): Haiku (fast/cheap) - basic queries, reads, straightforward operations
- MODERATE (31-70): Sonnet (balanced) - analysis, multi-step reasoning, standard operations
- COMPLEX (71-100): Opus (capable) - design, security, debugging, architecture decisions

Uses heuristics:
- Message length (longer = more complex)
- Tool count (more tools = more complex)
- Code presence (code operations need capable models)
- Keywords (design, security, debug, optimize, etc. indicate complexity)
"""

import logging
import re
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class ComplexityScore:
    """Result of complexity classification."""

    score: int  # 0-100
    confidence: float  # 0.0-1.0
    category: str  # "simple", "moderate", or "complex"
    reasoning: str  # Explanation of score
    indicators: Dict[str, Any]  # Breakdown of factors


class TaskComplexityClassifier:
    """Classifies request complexity for model routing."""

    # Keyword patterns that indicate complexity
    SIMPLE_KEYWORDS = {
        "read", "list", "get", "find", "extract", "check",
        "describe", "summarize", "count", "view", "show", "display",
        "fetch", "retrieve", "search", "locate"
    }

    MODERATE_KEYWORDS = {
        "analyze", "compare", "explain", "translate", "format",
        "convert", "parse", "filter", "sort", "group",
        "categorize", "classify", "identify", "validate"
    }

    COMPLEX_KEYWORDS = {
        "design", "architect", "plan", "optimize", "improve",
        "security", "vulnerability", "exploit", "debug",
        "troubleshoot", "diagnose", "refactor", "rewrite",
        "implement", "develop", "create", "build", "system",
        "algorithm", "strategy", "trade-off", "risk"
    }

    def classify_request_complexity(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Any]] = None,
        available_tool_count: int = 0
    ) -> ComplexityScore:
        """
        Classify the complexity of a request.

        Args:
            messages: Conversation messages (API format)
            tools: Available tools list (optional)
            available_tool_count: Number of available tools (optional)

        Returns:
            ComplexityScore with score (0-100), confidence, and reasoning
        """
        indicators = {}
        score_components = []

        # Extract text from messages
        message_text = self._extract_message_text(messages)
        indicators["message_length"] = len(message_text)

        # Analyze message length
        length_score = self._analyze_length(message_text)
        score_components.append(length_score)
        indicators["length_contribution"] = length_score

        # Analyze tool count
        tool_count = len(tools) if tools else available_tool_count
        tool_score = self._analyze_tool_count(tool_count)
        score_components.append(tool_score)
        indicators["tool_count"] = tool_count
        indicators["tool_contribution"] = tool_score

        # Analyze code presence
        code_score = self._analyze_code_presence(message_text)
        score_components.append(code_score)
        indicators["has_code"] = code_score > 0
        indicators["code_contribution"] = code_score

        # Analyze keywords
        keyword_score, keyword_type = self._analyze_keywords(message_text)
        score_components.append(keyword_score)
        indicators["dominant_keywords"] = keyword_type
        indicators["keyword_contribution"] = keyword_score

        # Analyze request structure
        structure_score = self._analyze_request_structure(messages)
        score_components.append(structure_score)
        indicators["structure_contribution"] = structure_score

        # Calculate weighted score
        weights = {
            "length": 0.15,
            "tools": 0.15,
            "code": 0.25,
            "keywords": 0.35,
            "structure": 0.10
        }

        weighted_score = (
            length_score * weights["length"] +
            tool_score * weights["tools"] +
            code_score * weights["code"] +
            keyword_score * weights["keywords"] +
            structure_score * weights["structure"]
        )

        # Normalize to 0-100
        final_score = int(weighted_score)
        final_score = max(0, min(100, final_score))

        # Determine category and confidence
        if final_score < 30:
            category = "simple"
            confidence = 0.85 if keyword_type == "simple" else 0.65
        elif final_score < 70:
            category = "moderate"
            confidence = 0.80
        else:
            category = "complex"
            confidence = 0.85 if keyword_type == "complex" else 0.70

        # Adjust confidence based on score variance
        score_variance = self._calculate_variance(score_components)
        if score_variance > 0.3:
            confidence *= 0.85  # Lower confidence if components disagree

        confidence = max(0.3, min(1.0, confidence))

        reasoning = self._generate_reasoning(
            final_score, category, indicators, keyword_type
        )

        logger.debug(
            "Task complexity classified: score=%d, category=%s, confidence=%.2f, "
            "indicators=%s",
            final_score, category, confidence, indicators
        )

        return ComplexityScore(
            score=final_score,
            confidence=confidence,
            category=category,
            reasoning=reasoning,
            indicators=indicators
        )

    def _extract_message_text(self, messages: List[Dict[str, Any]]) -> str:
        """Extract combined text from all messages."""
        texts = []
        for msg in messages:
            if isinstance(msg, dict):
                # Handle standard format
                if "content" in msg:
                    content = msg["content"]
                    if isinstance(content, str):
                        texts.append(content)
                    elif isinstance(content, list):
                        # Content blocks
                        for block in content:
                            if isinstance(block, dict) and "text" in block:
                                texts.append(block["text"])
                if "input" in msg:
                    texts.append(str(msg["input"]))
        return " ".join(texts)

    def _analyze_length(self, text: str) -> int:
        """Analyze message length. Longer messages = more complex."""
        length = len(text)
        if length < 100:
            return 10  # Very brief
        elif length < 300:
            return 25  # Short
        elif length < 800:
            return 45  # Medium
        elif length < 2000:
            return 65  # Long
        elif length < 5000:
            return 80  # Very long
        else:
            return 95  # Extremely long, likely complex analysis

    def _analyze_tool_count(self, tool_count: int) -> int:
        """Analyze tool availability. More tools = higher complexity potential."""
        if tool_count == 0:
            return 20  # No tools, likely simple
        elif tool_count < 5:
            return 35
        elif tool_count < 15:
            return 55
        elif tool_count < 30:
            return 70
        else:
            return 85  # Many tools, complex orchestration

    def _analyze_code_presence(self, text: str) -> int:
        """Detect code in the message. Code operations require capable models."""
        code_patterns = [
            r"```[\w]*\n",  # Code blocks
            r"def\s+\w+\(",  # Function definitions
            r"class\s+\w+",  # Class definitions
            r"import\s+\w+",  # Imports
            r"from\s+\w+\s+import",  # From imports
            r"\/\/|#",  # Comments
            r"\{\s*\w+\s*:\s*",  # Dict/object literals
            r"SELECT|INSERT|UPDATE|DELETE",  # SQL
            r"CREATE TABLE|ALTER|DROP",  # DDL
        ]

        code_score = 0
        for pattern in code_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                code_score = max(code_score, 50)
                if "security" in text.lower() or "vulnerability" in text.lower():
                    code_score = 85  # Security + code = complex
                break

        # Check for code-like structures
        if re.search(r"\w+\.\w+\(", text):  # Method calls
            code_score = max(code_score, 65)

        return code_score

    def _analyze_keywords(self, text: str) -> tuple[int, str]:
        """Analyze keyword presence to determine complexity."""
        text_lower = text.lower()

        # Check for complex keywords first
        complex_matches = sum(
            1 for kw in self.COMPLEX_KEYWORDS
            if kw in text_lower
        )

        # Check for moderate keywords
        moderate_matches = sum(
            1 for kw in self.MODERATE_KEYWORDS
            if kw in text_lower
        )

        # Check for simple keywords
        simple_matches = sum(
            1 for kw in self.SIMPLE_KEYWORDS
            if kw in text_lower
        )

        # Determine dominant keyword type
        if complex_matches > moderate_matches and complex_matches > simple_matches:
            # Complex keywords dominant
            score = min(95, 60 + (complex_matches * 5))
            keyword_type = "complex"
        elif moderate_matches > simple_matches:
            score = min(70, 40 + (moderate_matches * 5))
            keyword_type = "moderate"
        elif simple_matches > 0:
            score = min(40, 10 + (simple_matches * 3))
            keyword_type = "simple"
        else:
            # No clear keywords
            score = 40  # Default to moderate
            keyword_type = "neutral"

        return score, keyword_type

    def _analyze_request_structure(self, messages: List[Dict[str, Any]]) -> int:
        """Analyze request structure complexity."""
        score = 30  # Baseline for any structured request

        if len(messages) == 0:
            return 10  # Empty request is simple

        # Multiple turns indicate conversational complexity
        if len(messages) > 5:
            score += 15
        elif len(messages) > 1:
            score += 10

        # Check for nested structures, multiple questions
        last_message = messages[-1] if messages else {}
        if isinstance(last_message, dict):
            content = last_message.get("content", "")
            if isinstance(content, str):
                # Multiple questions/tasks in one message
                question_count = content.count("?")
                score += min(20, question_count * 5)

                # Bullet points or numbered lists indicate complexity
                if re.search(r"^[\-\*•]\s|\n[\d]+\.", content, re.MULTILINE):
                    score += 15

                # Multiple paragraphs
                paragraph_count = len(content.split("\n\n"))
                if paragraph_count > 3:
                    score += 10

        return min(100, score)

    def _calculate_variance(self, components: List[int]) -> float:
        """Calculate variance in score components."""
        if len(components) < 2:
            return 0.0

        mean = sum(components) / len(components)
        variance = sum((x - mean) ** 2 for x in components) / len(components)
        std_dev = variance ** 0.5

        # Return normalized standard deviation
        return std_dev / 100.0 if mean > 0 else 0.0

    def _generate_reasoning(
        self,
        score: int,
        category: str,
        indicators: Dict[str, Any],
        keyword_type: str
    ) -> str:
        """Generate human-readable reasoning for the classification."""
        parts = []

        # Main category reasoning
        if category == "simple":
            parts.append("Simple request: straightforward operation")
        elif category == "moderate":
            parts.append("Moderate complexity: multi-step reasoning required")
        else:
            parts.append("Complex request: deep reasoning or critical operations")

        # Add specific indicators
        if indicators.get("has_code"):
            parts.append("code present in request")

        if indicators.get("tool_count", 0) > 15:
            parts.append(f"high tool count ({indicators['tool_count']} tools)")

        if indicators.get("message_length", 0) > 2000:
            parts.append("lengthy request")

        if keyword_type in ["complex", "moderate"]:
            parts.append(f"{keyword_type} keywords detected")

        return "; ".join(parts)


def classify_request_complexity(
    messages: List[Dict[str, Any]],
    tools: Optional[List[Any]] = None,
    available_tool_count: int = 0
) -> ComplexityScore:
    """
    Convenience function to classify request complexity.

    Args:
        messages: Conversation messages
        tools: Available tools (optional)
        available_tool_count: Number of available tools (optional)

    Returns:
        ComplexityScore with score and category
    """
    classifier = TaskComplexityClassifier()
    return classifier.classify_request_complexity(messages, tools, available_tool_count)
