#!/usr/bin/env python3
"""
Platform Learning Engine for Hercules Orchestrator

Automatic learning and optimization across platforms based on historical traces.
Identifies patterns, detects regressions, and suggests improvements.

Integrates with:
- hercules_orchestrator.py (global metrics)
- langfuse_integration.py (trace data)
- agent/consensus/standing.py (reputation decay model)

Capabilities:
1. Pattern detection: What works best on each platform
2. Anomaly detection: When performance degrades
3. Recommendation generation: Suggested improvements
4. A/B testing: Track prompt/strategy variants
5. Automatic optimization: Apply learned strategies
"""

from __future__ import annotations

import json
import logging
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)


class AnomalyType(Enum):
    """Types of detected anomalies."""
    PERFORMANCE_DEGRADATION = "performance_degradation"
    ERROR_SPIKE = "error_spike"
    COST_SPIKE = "cost_spike"
    LATENCY_SPIKE = "latency_spike"
    TOOL_FAILURE = "tool_failure"
    CONSENSUS_FAILURE = "consensus_failure"


@dataclass
class Pattern:
    """A detected pattern across platforms."""
    pattern_id: str
    platform: str
    metric_name: str
    value: float
    confidence: float  # 0.0 to 1.0
    supporting_traces: int
    first_seen: datetime = field(default_factory=datetime.utcnow)
    last_seen: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "platform": self.platform,
            "metric_name": self.metric_name,
            "value": self.value,
            "confidence": self.confidence,
            "supporting_traces": self.supporting_traces,
            "age_hours": (datetime.utcnow() - self.first_seen).total_seconds() / 3600,
        }


@dataclass
class Anomaly:
    """A detected anomaly or regression."""
    anomaly_id: str
    anomaly_type: AnomalyType
    platform: str
    severity: float  # 0.0 to 1.0
    description: str
    metric_baseline: float
    metric_current: float
    detected_at: datetime = field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    suggested_actions: List[str] = field(default_factory=list)

    def is_active(self) -> bool:
        """Is this anomaly still active?"""
        return self.resolved_at is None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "anomaly_id": self.anomaly_id,
            "type": self.anomaly_type.value,
            "platform": self.platform,
            "severity": self.severity,
            "description": self.description,
            "baseline": self.metric_baseline,
            "current": self.metric_current,
            "age_minutes": (datetime.utcnow() - self.detected_at).total_seconds() / 60,
            "is_active": self.is_active(),
            "suggested_actions": self.suggested_actions,
        }


@dataclass
class Recommendation:
    """A suggested optimization."""
    recommendation_id: str
    platform: str
    category: str  # "prompt", "tools", "strategy", "parameters"
    title: str
    description: str
    expected_improvement: float  # Percentage improvement expected
    confidence: float  # 0.0 to 1.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    applied: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "platform": self.platform,
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "expected_improvement_percent": self.expected_improvement * 100,
            "confidence": self.confidence,
            "applied": self.applied,
        }


class PatternDetector:
    """Detects patterns from platform metrics."""

    def __init__(self, min_supporting_traces: int = 10):
        self.min_supporting_traces = min_supporting_traces
        self.patterns: Dict[str, Pattern] = {}
        self._lock = threading.RLock()

    def add_pattern(self, pattern: Pattern):
        """Register a detected pattern."""
        with self._lock:
            self.patterns[pattern.pattern_id] = pattern

    def get_patterns_for_platform(self, platform: str) -> List[Pattern]:
        """Get all patterns for a platform."""
        with self._lock:
            return [p for p in self.patterns.values() if p.platform == platform]

    def get_top_patterns(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get highest-confidence patterns."""
        with self._lock:
            sorted_patterns = sorted(
                self.patterns.values(),
                key=lambda p: p.confidence,
                reverse=True,
            )[:limit]
            return [p.to_dict() for p in sorted_patterns]


class AnomalyDetector:
    """Detects performance anomalies and regressions."""

    def __init__(self):
        self.anomalies: Dict[str, Anomaly] = {}
        self.baselines: Dict[str, Dict[str, float]] = defaultdict(dict)
        self._lock = threading.RLock()

    def set_baseline(self, platform: str, metric_name: str, value: float):
        """Set baseline for a metric."""
        with self._lock:
            self.baselines[platform][metric_name] = value

    def detect_anomaly(
        self,
        platform: str,
        metric_name: str,
        current_value: float,
        threshold_percent: float = 0.15,  # 15% change
    ) -> Optional[Anomaly]:
        """Detect if current value is anomalous vs baseline."""
        with self._lock:
            if platform not in self.baselines or metric_name not in self.baselines[platform]:
                # No baseline, can't detect
                return None

            baseline = self.baselines[platform][metric_name]
            change_percent = abs(current_value - baseline) / baseline if baseline != 0 else 0

            if change_percent > threshold_percent:
                severity = min(1.0, change_percent)
                is_degradation = current_value > baseline

                anomaly = Anomaly(
                    anomaly_id=f"{platform}_{metric_name}_{datetime.utcnow().timestamp()}",
                    anomaly_type=(
                        AnomalyType.PERFORMANCE_DEGRADATION
                        if is_degradation and "latency" in metric_name
                        else AnomalyType.ERROR_SPIKE
                        if is_degradation and "error" in metric_name
                        else AnomalyType.COST_SPIKE
                        if is_degradation and "cost" in metric_name
                        else AnomalyType.PERFORMANCE_DEGRADATION
                    ),
                    platform=platform,
                    severity=severity,
                    description=(
                        f"{metric_name} on {platform} changed {change_percent:.1%}: "
                        f"{baseline:.2f} → {current_value:.2f}"
                    ),
                    metric_baseline=baseline,
                    metric_current=current_value,
                )

                self.anomalies[anomaly.anomaly_id] = anomaly
                logger.warning(f"Anomaly detected: {anomaly.anomaly_id}")
                return anomaly

            return None

    def get_active_anomalies(self) -> List[Anomaly]:
        """Get all active anomalies."""
        with self._lock:
            return [a for a in self.anomalies.values() if a.is_active()]

    def resolve_anomaly(self, anomaly_id: str):
        """Mark anomaly as resolved."""
        with self._lock:
            if anomaly_id in self.anomalies:
                self.anomalies[anomaly_id].resolved_at = datetime.utcnow()

    def get_anomaly_history(
        self, platform: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get anomaly history for a platform."""
        with self._lock:
            platform_anomalies = [
                a for a in self.anomalies.values()
                if a.platform == platform
            ]
            sorted_anomalies = sorted(
                platform_anomalies,
                key=lambda a: a.detected_at,
                reverse=True,
            )[:limit]
            return [a.to_dict() for a in sorted_anomalies]


class RecommendationEngine:
    """Generates optimization recommendations based on patterns."""

    def __init__(self):
        self.recommendations: Dict[str, Recommendation] = {}
        self._lock = threading.RLock()

    def generate_recommendation(
        self,
        platform: str,
        category: str,
        title: str,
        description: str,
        expected_improvement: float,
        confidence: float,
    ) -> Recommendation:
        """Generate a recommendation."""
        with self._lock:
            rec = Recommendation(
                recommendation_id=f"{platform}_{category}_{datetime.utcnow().timestamp()}",
                platform=platform,
                category=category,
                title=title,
                description=description,
                expected_improvement=expected_improvement,
                confidence=confidence,
            )
            self.recommendations[rec.recommendation_id] = rec
            logger.info(f"Recommendation generated: {rec.recommendation_id}")
            return rec

    def get_recommendations(self, platform: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get recommendations, optionally filtered by platform."""
        with self._lock:
            recs = self.recommendations.values()
            if platform:
                recs = [r for r in recs if r.platform == platform]

            sorted_recs = sorted(
                recs,
                key=lambda r: r.confidence * r.expected_improvement,
                reverse=True,
            )
            return [r.to_dict() for r in sorted_recs]

    def apply_recommendation(self, recommendation_id: str):
        """Mark recommendation as applied."""
        with self._lock:
            if recommendation_id in self.recommendations:
                self.recommendations[recommendation_id].applied = True
                logger.info(f"Recommendation applied: {recommendation_id}")


class PlatformLearningEngine:
    """Main learning engine coordinating all analysis."""

    def __init__(self):
        self.pattern_detector = PatternDetector()
        self.anomaly_detector = AnomalyDetector()
        self.recommendation_engine = RecommendationEngine()
        self._lock = threading.RLock()

    def analyze_platform_metrics(
        self,
        platform: str,
        success_rate: float,
        avg_response_time_ms: float,
        avg_cost_per_conversation: float,
        error_rate: float,
    ):
        """Analyze metrics and trigger learning."""
        # Set baselines on first run
        self.anomaly_detector.set_baseline(platform, "success_rate", success_rate)
        self.anomaly_detector.set_baseline(platform, "latency_ms", avg_response_time_ms)
        self.anomaly_detector.set_baseline(platform, "cost", avg_cost_per_conversation)
        self.anomaly_detector.set_baseline(platform, "error_rate", error_rate)

        # Detect anomalies
        anomalies = []
        for metric_name, value in [
            ("latency_ms", avg_response_time_ms),
            ("cost", avg_cost_per_conversation),
            ("error_rate", error_rate),
        ]:
            anomaly = self.anomaly_detector.detect_anomaly(
                platform, metric_name, value
            )
            if anomaly:
                anomalies.append(anomaly)

        # Generate recommendations if anomalies detected
        if anomalies:
            for anomaly in anomalies:
                if anomaly.anomaly_type == AnomalyType.LATENCY_SPIKE:
                    self.recommendation_engine.generate_recommendation(
                        platform=platform,
                        category="parameters",
                        title="Reduce model context window",
                        description=(
                            f"Latency spiked on {platform}. "
                            "Consider reducing context to speed up responses."
                        ),
                        expected_improvement=0.20,
                        confidence=0.7,
                    )
                elif anomaly.anomaly_type == AnomalyType.ERROR_SPIKE:
                    self.recommendation_engine.generate_recommendation(
                        platform=platform,
                        category="strategy",
                        title="Increase retry attempts",
                        description=(
                            f"Error rate increased on {platform}. "
                            "Consider adding more retry logic."
                        ),
                        expected_improvement=0.15,
                        confidence=0.6,
                    )
                elif anomaly.anomaly_type == AnomalyType.COST_SPIKE:
                    self.recommendation_engine.generate_recommendation(
                        platform=platform,
                        category="prompt",
                        title="Optimize prompt brevity",
                        description=(
                            f"Cost per conversation increased on {platform}. "
                            "Try shortening prompts while maintaining quality."
                        ),
                        expected_improvement=0.25,
                        confidence=0.75,
                    )

    def get_learning_summary(self) -> Dict[str, Any]:
        """Get summary of all learning."""
        with self._lock:
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "patterns": self.pattern_detector.get_top_patterns(5),
                "active_anomalies": [
                    a.to_dict() for a in self.anomaly_detector.get_active_anomalies()
                ],
                "recommendations": self.recommendation_engine.get_recommendations(),
                "stats": {
                    "total_patterns": len(self.pattern_detector.patterns),
                    "total_anomalies": len(self.anomaly_detector.anomalies),
                    "total_recommendations": len(self.recommendation_engine.recommendations),
                },
            }
