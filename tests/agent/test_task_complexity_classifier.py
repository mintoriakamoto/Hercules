"""Tests for task complexity classification."""

import pytest

from agent.routing.task_classifier import (
    TaskComplexityClassifier,
    ComplexityScore,
    classify_request_complexity,
)


class TestTaskComplexityClassifier:
    """Test task complexity classification."""

    def test_classifier_initialization(self):
        """Test that classifier initializes properly."""
        classifier = TaskComplexityClassifier()
        assert classifier is not None
        assert len(classifier.SIMPLE_KEYWORDS) > 0
        assert len(classifier.MODERATE_KEYWORDS) > 0
        assert len(classifier.COMPLEX_KEYWORDS) > 0

    def test_simple_task_classification(self):
        """Test classification of simple tasks."""
        classifier = TaskComplexityClassifier()
        messages = [{"role": "user", "content": "Read the file and extract the first line"}]

        score = classifier.classify_request_complexity(messages)

        assert isinstance(score, ComplexityScore)
        assert score.score < 35  # Should be simple (0-30)
        assert score.category == "simple"
        assert score.confidence > 0.5

    def test_moderate_task_classification(self):
        """Test classification of moderate tasks."""
        classifier = TaskComplexityClassifier()
        messages = [{"role": "user", "content": "Analyze this log file and find errors"}]

        score = classifier.classify_request_complexity(messages)

        assert isinstance(score, ComplexityScore)
        assert 25 < score.score < 75  # Should be moderate
        assert score.category in ["simple", "moderate"]
        assert score.confidence > 0.3

    def test_complex_task_classification(self):
        """Test classification of complex tasks."""
        classifier = TaskComplexityClassifier()
        messages = [
            {
                "role": "user",
                "content": "Design a secure authentication system with trade-off analysis between OAuth2, SAML, and JWT"
            }
        ]

        score = classifier.classify_request_complexity(messages)

        assert isinstance(score, ComplexityScore)
        assert score.score > 50  # Should be complex
        assert score.category in ["complex", "moderate"]
        assert score.confidence > 0.4

    def test_code_detection(self):
        """Test detection of code in messages."""
        classifier = TaskComplexityClassifier()

        # Simple read task
        simple_msg = [{"role": "user", "content": "List the files"}]
        simple_score = classifier.classify_request_complexity(simple_msg)

        # Code task
        code_msg = [
            {"role": "user", "content": """
            def calculate(x):
                return x * 2
            What does this function do?
            """}
        ]
        code_score = classifier.classify_request_complexity(code_msg)

        # Code should score higher due to code presence
        assert code_score.score > simple_score.score

    def test_security_keyword_detection(self):
        """Test detection of security-related keywords."""
        classifier = TaskComplexityClassifier()

        messages = [
            {
                "role": "user",
                "content": "Find security vulnerabilities in this authentication system"
            }
        ]

        score = classifier.classify_request_complexity(messages)

        assert score.score > 60  # Security tasks should score high
        assert "security" in score.indicators.get("dominant_keywords", "").lower() or score.score > 60

    def test_long_message_complexity(self):
        """Test that longer messages score as more complex."""
        classifier = TaskComplexityClassifier()

        short_msg = [{"role": "user", "content": "Read file"}]
        short_score = classifier.classify_request_complexity(short_msg)

        long_msg = [
            {"role": "user", "content": "Read file " + "and analyze it " * 100}
        ]
        long_score = classifier.classify_request_complexity(long_msg)

        # Longer message should score higher
        assert long_score.score > short_score.score

    def test_multiple_tools_complexity(self):
        """Test that more tools increase complexity."""
        classifier = TaskComplexityClassifier()

        messages = [{"role": "user", "content": "Help me"}]

        # With few tools
        few_tools = [{"name": "read", "description": "Read"}]
        score_few = classifier.classify_request_complexity(messages, tools=few_tools)

        # With many tools
        many_tools = [
            {"name": f"tool_{i}", "description": f"Tool {i}"}
            for i in range(30)
        ]
        score_many = classifier.classify_request_complexity(messages, tools=many_tools)

        # More tools should increase complexity
        assert score_many.score > score_few.score

    def test_complexity_score_range(self):
        """Test that complexity score is always 0-100."""
        classifier = TaskComplexityClassifier()

        test_cases = [
            "Read",
            "Help me",
            "Design a system",
            "x" * 5000,
            "",
        ]

        for content in test_cases:
            messages = [{"role": "user", "content": content}]
            score = classifier.classify_request_complexity(messages)

            assert 0 <= score.score <= 100, f"Score {score.score} out of range for '{content[:50]}'"
            assert 0.0 <= score.confidence <= 1.0, f"Confidence {score.confidence} out of range"
            assert score.category in ["simple", "moderate", "complex"]

    def test_confidence_varies_with_clarity(self):
        """Test that confidence is higher for clear classifications."""
        classifier = TaskComplexityClassifier()

        # Clear simple task
        clear_simple = [{"role": "user", "content": "Read the file list"}]
        simple_score = classifier.classify_request_complexity(clear_simple)

        # Ambiguous task
        ambiguous = [{"role": "user", "content": "Do something useful"}]
        ambiguous_score = classifier.classify_request_complexity(ambiguous)

        # Clear task should have higher or equal confidence
        assert simple_score.confidence >= ambiguous_score.confidence - 0.1

    def test_multi_turn_conversation(self):
        """Test classification with multi-turn conversation."""
        classifier = TaskComplexityClassifier()

        messages = [
            {"role": "user", "content": "Read the file"},
            {"role": "assistant", "content": "Done"},
            {"role": "user", "content": "Now analyze it in detail"}
        ]

        score = classifier.classify_request_complexity(messages)

        assert score.score > 30  # Multi-turn should increase complexity
        assert score.indicators["message_length"] > 0

    def test_convenience_function(self):
        """Test the convenience function."""
        messages = [{"role": "user", "content": "Read file"}]

        score = classify_request_complexity(messages)

        assert isinstance(score, ComplexityScore)
        assert score.score < 50

    def test_indicators_populated(self):
        """Test that indicators are properly populated."""
        classifier = TaskComplexityClassifier()
        messages = [
            {"role": "user", "content": """
            def func():
                pass
            What does this do?
            """
            }
        ]

        score = classifier.classify_request_complexity(messages)

        assert "message_length" in score.indicators
        assert "tool_count" in score.indicators
        assert "has_code" in score.indicators
        assert "dominant_keywords" in score.indicators
        assert "structure_contribution" in score.indicators


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
