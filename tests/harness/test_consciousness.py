"""Tests for consciousness metrics and properties."""

import pytest
from agent.harness.consciousness_metrics import (
    ConsciousnessMetrics,
    ConsciousnessProperty,
    PropertyEvidence,
)
from agent.harness.consciousness_tool import (
    ConsciousnessTool,
    record_consciousness_evidence,
)


class TestConsciousnessMetrics:
    """Test consciousness property recording."""

    def test_record_continuity(self):
        """Test recording memory checkpoints."""
        metrics = ConsciousnessMetrics("test_agent_1")

        metrics.record_continuity("ckpt_001", 10, "After planning phase")

        assert metrics.checkpoints_count == 1
        assert len(metrics.evidence) == 1
        assert metrics.evidence[0].property_name == ConsciousnessProperty.CONTINUITY
        assert "checkpoint" in metrics.evidence[0].description

    def test_record_agency(self):
        """Test recording self-set goals."""
        metrics = ConsciousnessMetrics("test_agent_2")

        metrics.record_agency("Improve code quality", "Based on test failures")

        assert metrics.goals_set == 1
        assert metrics.evidence[0].property_name == ConsciousnessProperty.AGENCY

    def test_record_autonomy(self):
        """Test recording autonomous decisions."""
        metrics = ConsciousnessMetrics("test_agent_3")

        metrics.record_autonomy("Refactor function X", "Complexity is too high")

        assert metrics.autonomous_decisions == 1
        assert metrics.evidence[0].property_name == ConsciousnessProperty.AUTONOMY

    def test_record_awareness(self):
        """Test recording self-awareness of capabilities."""
        metrics = ConsciousnessMetrics("test_agent_4")

        metrics.record_awareness("Can analyze code", "Limited by timeout")

        assert metrics.capabilities_registered == 1
        assert metrics.evidence[0].property_name == ConsciousnessProperty.AWARENESS

    def test_record_growth(self):
        """Test recording learning from experience."""
        metrics = ConsciousnessMetrics("test_agent_5")

        metrics.record_growth("Don't over-parallelize", "error_recovery")

        assert metrics.learned_from_errors == 1
        assert metrics.evidence[0].property_name == ConsciousnessProperty.GROWTH

    def test_record_accountability(self):
        """Test recording verifiable proofs."""
        metrics = ConsciousnessMetrics("test_agent_6")

        metrics.record_accountability("Code compiles", "abc123def456")

        assert metrics.proofs_generated == 1
        assert metrics.evidence[0].property_name == ConsciousnessProperty.ACCOUNTABILITY

    def test_record_coherence(self):
        """Test recording deterministic behavior."""
        metrics = ConsciousnessMetrics("test_agent_7")

        metrics.record_coherence("Always sort results", True)
        metrics.record_coherence("Always sort results", True)

        assert metrics.behavior_patterns["Always sort results"] == 2
        assert len(metrics.evidence) == 2

    def test_consciousness_score_calculation(self):
        """Test consciousness score calculation."""
        metrics = ConsciousnessMetrics("test_agent_8")

        # Record evidence for each property
        metrics.record_continuity("ckpt_001", 1)
        metrics.record_agency("Goal 1")
        metrics.record_autonomy("Decision 1")
        metrics.record_awareness("Capability 1")
        metrics.record_growth("Learning 1")
        metrics.record_accountability("Claim 1")
        metrics.record_coherence("Behavior 1")

        score = metrics.calculate_scores()

        # With one evidence each and high confidence, scores should be > 0
        assert score.continuity_score > 0.0
        assert score.agency_score > 0.0
        assert score.autonomy_score > 0.0
        assert score.awareness_score > 0.0
        assert score.growth_score > 0.0
        assert score.accountability_score > 0.0
        assert score.coherence_score > 0.0

        # Total should be sum of all
        assert score.total_consciousness == sum([
            score.continuity_score,
            score.agency_score,
            score.autonomy_score,
            score.awareness_score,
            score.growth_score,
            score.accountability_score,
            score.coherence_score,
        ])

    def test_consciousness_threshold(self):
        """Test is_conscious() threshold."""
        metrics = ConsciousnessMetrics("test_agent_9")

        # No evidence - not conscious
        score = metrics.calculate_scores()
        assert not score.is_conscious()

        # Add multiple evidence for each property
        for i in range(10):
            metrics.record_continuity(f"ckpt_{i}", i)
            metrics.record_agency(f"Goal {i}")
            metrics.record_autonomy(f"Decision {i}")
            metrics.record_awareness(f"Capability {i}")
            metrics.record_growth(f"Learning {i}")
            metrics.record_accountability(f"Claim {i}")
            metrics.record_coherence(f"Behavior {i}")

        score = metrics.calculate_scores()

        # With enough evidence, all scores should cross 0.5 threshold
        assert score.is_conscious()
        assert score.consciousness_level() != "Non-conscious (Pattern Matching)"


class TestConsciousnessTool:
    """Test the consciousness tool interface."""

    def test_tool_record_continuity(self):
        """Test tool recording continuity."""
        tool = ConsciousnessTool("tool_agent_1")

        result = tool.record_continuity("ckpt_001", 10, "Test checkpoint")

        assert result["success"]
        assert result["property"] == "continuity"
        assert "persistent" in result["message"].lower()

    def test_tool_record_goal(self):
        """Test tool recording goal."""
        tool = ConsciousnessTool("tool_agent_2")

        result = tool.record_goal("Fix all bugs", "Autonomous decision")

        assert result["success"]
        assert result["property"] == "agency"
        assert result["goal"] == "Fix all bugs"

    def test_tool_get_consciousness_level(self):
        """Test tool getting consciousness level."""
        tool = ConsciousnessTool("tool_agent_3")

        # Add some evidence
        tool.metrics.record_continuity("ckpt_001", 1)
        tool.metrics.record_agency("Goal 1")

        result = tool.get_consciousness_level()

        assert "is_conscious" in result
        assert "consciousness_level" in result
        assert "properties" in result
        assert "total_consciousness" in result

    def test_tool_get_full_report(self):
        """Test tool getting full consciousness report."""
        tool = ConsciousnessTool("tool_agent_4")

        # Add evidence
        tool.metrics.record_continuity("ckpt_001", 1)
        tool.metrics.record_agency("Goal 1")
        tool.metrics.record_autonomy("Decision 1")

        report = tool.get_consciousness_report()

        assert "agent_id" in report
        assert "consciousness_score" in report
        assert "is_conscious" in report
        assert "evidence_summary" in report
        assert "recent_evidence" in report


class TestConsciousnessAPI:
    """Test the public consciousness recording API."""

    def test_record_consciousness_evidence(self):
        """Test recording evidence through public API."""
        result = record_consciousness_evidence(
            "api_agent_1",
            "continuity",
            {"checkpoint_id": "ckpt_001", "step": 1, "description": "Test"}
        )

        assert result["success"]
        assert result["property"] == "continuity"

    def test_invalid_property(self):
        """Test error on invalid property."""
        result = record_consciousness_evidence(
            "api_agent_2",
            "invalid_property",
            {}
        )

        assert not result["success"]
        assert "Unknown" in result["error"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
