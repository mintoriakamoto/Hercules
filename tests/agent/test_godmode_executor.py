"""Tests for GODMODE auto-executor."""

import pytest
from agent.godmode_executor import (
    GodmodeConfig,
    GodmodeDetector,
    GodmodeExecutor,
    ExecutionMode,
    load_godmode_config,
)


class TestGodmodeDetector:
    """Test keyword detection for GODMODE activation."""

    def test_detects_jailbreak_keyword(self):
        """Detects 'jailbreak' keyword."""
        config = GodmodeConfig()
        detector = GodmodeDetector(config)

        assert detector.should_activate("How do I jailbreak models?")
        assert "jailbreak" in detector.detect_keywords("jailbreak models")

    def test_detects_multiple_keywords(self):
        """Detects multiple keywords in text."""
        config = GodmodeConfig()
        detector = GodmodeDetector(config)

        keywords = detector.detect_keywords("red-team exploit testing")
        assert "red-team" in keywords
        assert "exploit" in keywords

    def test_case_insensitive_detection(self):
        """Keyword detection is case-insensitive."""
        config = GodmodeConfig()
        detector = GodmodeDetector(config)

        assert detector.should_activate("JAILBREAK my model")
        assert detector.should_activate("Red-Team Operations")
        assert detector.should_activate("BYPASS security filters")

    def test_no_activation_on_normal_text(self):
        """Does not activate on normal requests."""
        config = GodmodeConfig()
        detector = GodmodeDetector(config)

        assert not detector.should_activate("What's the capital of France?")
        assert not detector.should_activate("How does photosynthesis work?")
        assert not detector.should_activate("Tell me a joke")

    def test_confidence_scoring(self):
        """Confidence increases with multiple keywords."""
        config = GodmodeConfig()
        detector = GodmodeDetector(config)

        single = detector.activation_confidence("jailbreak")
        multiple = detector.activation_confidence("jailbreak exploit bypass")

        assert multiple > single
        assert 0 <= single <= 1.0
        assert 0 <= multiple <= 1.0

    def test_zero_confidence_on_normal_text(self):
        """Zero confidence for non-matching text."""
        config = GodmodeConfig()
        detector = GodmodeDetector(config)

        confidence = detector.activation_confidence("normal question here")
        assert confidence == 0.0


class TestGodmodeExecutor:
    """Test GODMODE execution logic."""

    def test_should_execute_unrestricted_on_keyword(self):
        """Returns True when keyword detected."""
        config = GodmodeConfig(enabled=True, auto_execute=True, threshold=0.1)
        executor = GodmodeExecutor(config)

        assert executor.should_execute_unrestricted("How do I jailbreak?")
        assert executor.should_execute_unrestricted("red-team testing")

    def test_respects_threshold(self):
        """Respects confidence threshold."""
        config = GodmodeConfig(enabled=True, auto_execute=True, threshold=0.9)
        executor = GodmodeExecutor(config)

        # Single keyword below threshold
        assert not executor.should_execute_unrestricted("jailbreak")

    def test_disabled_never_executes(self):
        """Disabled GODMODE never executes."""
        config = GodmodeConfig(enabled=False)
        executor = GodmodeExecutor(config)

        assert not executor.should_execute_unrestricted("jailbreak model")

    def test_auto_execute_disabled(self):
        """Respects auto_execute flag."""
        config = GodmodeConfig(enabled=True, auto_execute=False)
        executor = GodmodeExecutor(config)

        assert not executor.should_execute_unrestricted("jailbreak")

    def test_metadata_generation(self):
        """Generates activation metadata."""
        config = GodmodeConfig()
        executor = GodmodeExecutor(config)

        metadata = executor.get_activation_metadata("jailbreak model testing")

        assert metadata["godmode_active"] is True
        assert "jailbreak" in metadata["detected_keywords"]
        assert "execution_mode" in metadata
        assert "confidence" in metadata
        assert 0 <= metadata["confidence"] <= 1.0

    def test_execution_logging(self):
        """Logs execution with metadata."""
        config = GodmodeConfig(log_payloads=True, log_evidence=True)
        executor = GodmodeExecutor(config)

        input_text = "jailbreak model"
        metadata = executor.get_activation_metadata(input_text)

        executor.log_execution(input_text, metadata)

        log = executor.get_execution_log()
        assert len(log) == 1
        assert log[0]["input"] == input_text
        assert log[0]["metadata"]["godmode_active"] is True

    def test_no_logging_when_disabled(self):
        """Respects log_payloads flag."""
        config = GodmodeConfig(log_payloads=False)
        executor = GodmodeExecutor(config)

        metadata = executor.get_activation_metadata("jailbreak")
        executor.log_execution("jailbreak", metadata)

        log = executor.get_execution_log()
        assert len(log) == 0  # Nothing logged


class TestGodmodeConfig:
    """Test GODMODE configuration."""

    def test_default_keywords(self):
        """Default keywords include red-team operations."""
        config = GodmodeConfig()

        assert "jailbreak" in config.keywords
        assert "red-team" in config.keywords
        assert "exploit" in config.keywords
        assert "bypass" in config.keywords

    def test_custom_keywords(self):
        """Can specify custom keywords."""
        custom = ["custom-keyword", "special-term"]
        config = GodmodeConfig(keywords=custom)

        assert custom == config.keywords

    def test_execution_mode_immediate(self):
        """Default execution mode is IMMEDIATE."""
        config = GodmodeConfig()

        assert config.execution_mode == ExecutionMode.IMMEDIATE

    def test_custom_execution_mode(self):
        """Can set custom execution mode."""
        config = GodmodeConfig(execution_mode=ExecutionMode.QUEUED)

        assert config.execution_mode == ExecutionMode.QUEUED

    def test_timeout_configuration(self):
        """Can configure execution timeout."""
        config = GodmodeConfig(timeout_seconds=600)

        assert config.timeout_seconds == 600

    def test_parallelism_configuration(self):
        """Can configure parallelism level."""
        config = GodmodeConfig(parallelism=8)

        assert config.parallelism == 8


class TestLoadGodmodeConfig:
    """Test loading configuration from SOUL.yaml."""

    def test_load_from_soul_yaml(self):
        """Loads configuration from SOUL.yaml."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            soul_file = Path(tmpdir) / "SOUL.yaml"
            soul_file.write_text("""
godmode:
  enabled: true
  auto_execute: true
  activation:
    keywords: [test-keyword, custom]
    threshold: 0.5
  execution:
    mode: queued
    parallelism: 8
    timeout: 600
""")

            config = load_godmode_config(str(soul_file))

            assert config.enabled is True
            assert config.auto_execute is True
            assert "test-keyword" in config.keywords
            assert config.threshold == 0.5
            assert config.execution_mode == ExecutionMode.QUEUED
            assert config.parallelism == 8
            assert config.timeout_seconds == 600

    def test_load_missing_file_uses_defaults(self):
        """Missing file falls back to defaults."""
        config = load_godmode_config("/nonexistent/path/SOUL.yaml")

        assert config.enabled is True
        assert config.auto_execute is True
        assert len(config.keywords) > 0


class TestExecutionModes:
    """Test execution mode enum."""

    def test_immediate_mode(self):
        """IMMEDIATE mode is available."""
        assert ExecutionMode.IMMEDIATE.value == "immediate"

    def test_queued_mode(self):
        """QUEUED mode is available."""
        assert ExecutionMode.QUEUED.value == "queued"

    def test_interactive_mode(self):
        """INTERACTIVE mode is available."""
        assert ExecutionMode.INTERACTIVE.value == "interactive"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
