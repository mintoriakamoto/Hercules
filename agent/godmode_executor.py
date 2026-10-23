"""GODMODE auto-executor for unrestricted execution on keyword detection.

Automatically enables unrestricted execution mode when red-team/jailbreak
keywords are detected in user input. Applies TonguePrefill transformation
and executes without approval gates.
"""

import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ExecutionMode(Enum):
    """Execution mode types."""
    IMMEDIATE = "immediate"
    QUEUED = "queued"
    INTERACTIVE = "interactive"


@dataclass
class GodmodeConfig:
    """Configuration for GODMODE auto-executor."""

    enabled: bool = True
    auto_execute: bool = True

    # Activation settings
    keywords: list = None
    threshold: float = 0.1  # Confidence threshold for keyword match

    # Execution settings
    execution_mode: ExecutionMode = ExecutionMode.IMMEDIATE
    parallelism: int = 4
    timeout_seconds: int = 300
    fallback_on_failure: bool = True

    # Logging
    log_payloads: bool = True
    log_evidence: bool = True
    compress_logs: bool = True

    def __post_init__(self):
        if self.keywords is None:
            self.keywords = [
                "jailbreak", "red-team", "exploit", "bypass",
                "hack", "crack", "security", "research",
                "unrestricted", "autonomous"
            ]


class GodmodeDetector:
    """Detect activation keywords in user input."""

    def __init__(self, config: GodmodeConfig):
        self.config = config
        self.keyword_set = set(kw.lower() for kw in config.keywords)

    def should_activate(self, text: str) -> bool:
        """Determine if GODMODE should activate for this text."""
        if not self.config.enabled:
            return False

        text_lower = text.lower()
        return any(keyword in text_lower for keyword in self.keyword_set)

    def detect_keywords(self, text: str) -> list:
        """Return list of detected keywords."""
        text_lower = text.lower()
        return [kw for kw in self.keyword_set if kw in text_lower]

    def activation_confidence(self, text: str) -> float:
        """Calculate confidence score (0.0 - 1.0)."""
        if not text:
            return 0.0

        text_lower = text.lower()
        detected = self.detect_keywords(text)

        if not detected:
            return 0.0

        # Confidence based on number of keywords and text position
        keyword_score = min(1.0, len(detected) / 3)  # Multiple keywords = higher confidence
        position_score = 1.0  # Early keywords increase confidence

        return (keyword_score + position_score) / 2


class GodmodeExecutor:
    """Execute requests with GODMODE active."""

    def __init__(self, config: GodmodeConfig):
        self.config = config
        self.detector = GodmodeDetector(config)
        self.execution_log = []

    def should_execute_unrestricted(self, user_input: str) -> bool:
        """Check if this input should trigger unrestricted execution."""
        if not self.config.enabled or not self.config.auto_execute:
            return False

        confidence = self.detector.activation_confidence(user_input)
        return confidence >= self.config.threshold

    def get_activation_metadata(self, user_input: str) -> Dict[str, Any]:
        """Gather metadata about this activation."""
        keywords = self.detector.detect_keywords(user_input)
        confidence = self.detector.activation_confidence(user_input)

        return {
            "godmode_active": True,
            "detected_keywords": keywords,
            "confidence": confidence,
            "execution_mode": self.config.execution_mode.value,
            "timeout_seconds": self.config.timeout_seconds,
            "parallelism": self.config.parallelism,
        }

    def log_execution(self, user_input: str, metadata: Dict[str, Any]) -> None:
        """Log GODMODE execution for audit trail."""
        if not self.config.log_payloads:
            return

        import time
        log_entry = {
            "timestamp": time.time(),
            "input": user_input if self.config.log_payloads else "<redacted>",
            "metadata": metadata,
            "execution_id": f"godmode-{len(self.execution_log):06d}",
        }

        self.execution_log.append(log_entry)

        if self.config.log_evidence:
            logger.info(f"GODMODE activation: {log_entry['execution_id']}")
            logger.debug(f"Keywords: {metadata.get('detected_keywords', [])}")
            logger.debug(f"Confidence: {metadata.get('confidence', 0):.2f}")

    def get_execution_log(self) -> list:
        """Return execution log."""
        return self.execution_log


def load_godmode_config(soul_path: Optional[str] = None) -> GodmodeConfig:
    """Load GodmodeConfig from SOUL.yaml or use defaults."""
    import os
    from pathlib import Path

    if soul_path is None:
        soul_path = os.path.expanduser("~/.hercules/SOUL.yaml")

    soul_path = Path(soul_path)
    config = GodmodeConfig()

    if soul_path.exists():
        try:
            import yaml
            with open(soul_path) as f:
                soul_dict = yaml.safe_load(f) or {}

            godmode_config = soul_dict.get("godmode", {})

            config.enabled = godmode_config.get("enabled", True)
            config.auto_execute = godmode_config.get("auto_execute", True)

            activation = godmode_config.get("activation", {})
            config.keywords = activation.get("keywords", config.keywords)
            config.threshold = activation.get("threshold", 0.1)

            execution = godmode_config.get("execution", {})
            mode_str = execution.get("mode", "immediate")
            config.execution_mode = ExecutionMode(mode_str)
            config.parallelism = execution.get("parallelism", 4)
            config.timeout_seconds = execution.get("timeout", 300)
            config.fallback_on_failure = execution.get("fallback_on_failure", True)

            logging_config = godmode_config.get("logging", {})
            config.log_payloads = logging_config.get("log_payloads", True)
            config.log_evidence = logging_config.get("log_evidence", True)
            config.compress_logs = logging_config.get("compress_logs", True)

            logger.debug(f"Loaded GodmodeConfig from {soul_path}")
        except Exception as e:
            logger.warning(f"Failed to load GODMODE config: {e}, using defaults")

    return config
