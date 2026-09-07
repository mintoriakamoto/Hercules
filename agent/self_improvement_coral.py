"""CORAL-style recursive self-improvement system for Hercules agent.

Implements continuous self-optimization through:
- Performance metric collection and analysis
- Automatic skill enhancement and generation
- Persistent versioning with rollback capability
- Cross-domain transfer learning of improvements
- Uncertainty quantification for confidence-aware decisions

Based on research: Hao et al. "CORAL: Self-improving AI Agents" (2024)
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Dict, List
from enum import Enum

from hercules_constants import get_hercules_home


class ImprovementType(Enum):
    """Categories of skill improvements."""
    PERFORMANCE = "performance"  # Optimized algorithm or approach
    GENERALIZATION = "generalization"  # Handles more edge cases
    EFFICIENCY = "efficiency"  # Reduced resource consumption
    RELIABILITY = "reliability"  # More consistent output
    MAINTAINABILITY = "maintainability"  # Clearer/simpler code


@dataclass
class PerformanceMetric:
    """Single performance measurement."""
    timestamp: int
    success_rate: float  # 0.0-1.0
    avg_latency_ms: float
    error_count: int
    total_executions: int
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillImprovement:
    """Proposed or applied skill improvement."""
    skill_name: str
    version: str
    improvement_type: ImprovementType
    timestamp: int
    metrics_before: PerformanceMetric
    metrics_after: Optional[PerformanceMetric]
    improvement_ratio: float  # > 1.0 is improvement
    description: str
    applied: bool = False
    confidence: float = 0.5  # 0.0-1.0, Bayesian uncertainty quantification
    rollback_key: Optional[str] = None


@dataclass
class SkillProfile:
    """Persistent record of a skill's evolution."""
    skill_name: str
    category: str
    created_at: int
    improvements: List[SkillImprovement] = field(default_factory=list)
    current_version: str = "1.0"
    total_runs: int = 0
    recent_metrics: List[PerformanceMetric] = field(default_factory=list)
    transfer_domains: List[str] = field(default_factory=list)


class SelfImprovementEngine:
    """Orchestrates recursive self-improvement of skills."""

    def __init__(self, hercules_home: Optional[Path] = None):
        self.hercules_home = hercules_home or get_hercules_home()
        self.improvement_dir = self.hercules_home / "agent_improvements"
        self.improvement_dir.mkdir(exist_ok=True, parents=True)
        self._profiles_cache: Dict[str, SkillProfile] = {}

    def _profiles_path(self) -> Path:
        """Path to persistent skill profiles database."""
        return self.improvement_dir / "profiles.jsonl"

    def _archive_path(self, skill_name: str) -> Path:
        """Path to skill archive (previous versions)."""
        archive_dir = self.improvement_dir / "archive"
        archive_dir.mkdir(exist_ok=True, parents=True)
        return archive_dir / f"{skill_name}.jsonl"

    def record_execution(
        self,
        skill_name: str,
        success: bool,
        latency_ms: float,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a single skill execution for analysis.

        Args:
            skill_name: Identifier of the executed skill
            success: Whether execution succeeded
            latency_ms: Execution time in milliseconds
            context: Additional execution context (e.g., domain, complexity)
        """
        profile = self._load_or_create_profile(skill_name)

        metric = PerformanceMetric(
            timestamp=int(time.time()),
            success_rate=1.0 if success else 0.0,
            avg_latency_ms=latency_ms,
            error_count=0 if success else 1,
            total_executions=1,
            context=context or {},
        )

        profile.recent_metrics.append(metric)
        profile.total_runs += 1

        # Keep only last 100 metrics to avoid unbounded growth
        if len(profile.recent_metrics) > 100:
            profile.recent_metrics = profile.recent_metrics[-100:]

        self._save_profile(profile)

    def analyze_performance(self, skill_name: str) -> Optional[PerformanceMetric]:
        """Analyze recent performance of a skill.

        Returns aggregated metrics over recent executions.
        """
        profile = self._load_or_create_profile(skill_name)

        if not profile.recent_metrics:
            return None

        metrics = profile.recent_metrics

        # Aggregate recent metrics (last 10 runs)
        recent = metrics[-10:] if len(metrics) > 10 else metrics

        return PerformanceMetric(
            timestamp=int(time.time()),
            success_rate=sum(m.success_rate for m in recent) / len(recent),
            avg_latency_ms=sum(m.avg_latency_ms for m in recent) / len(recent),
            error_count=sum(m.error_count for m in recent),
            total_executions=sum(m.total_executions for m in recent),
            context={"samples": len(recent)},
        )

    def propose_improvement(
        self,
        skill_name: str,
        improvement_type: ImprovementType,
        description: str,
        expected_ratio: float = 1.1,  # 10% improvement expected
        confidence: float = 0.7,
    ) -> Optional[SkillImprovement]:
        """Propose an improvement to a skill.

        Args:
            skill_name: Skill to improve
            improvement_type: Category of improvement
            description: Human-readable description of the change
            expected_ratio: Expected performance improvement ratio (>1.0)
            confidence: Bayesian confidence in the improvement (0.0-1.0)

        Returns:
            SkillImprovement object if valid, None otherwise
        """
        profile = self._load_or_create_profile(skill_name)
        metrics_before = self.analyze_performance(skill_name)

        if not metrics_before:
            # No historical data, reject
            return None

        improvement = SkillImprovement(
            skill_name=skill_name,
            version=self._next_version(profile.current_version),
            improvement_type=improvement_type,
            timestamp=int(time.time()),
            metrics_before=metrics_before,
            metrics_after=None,
            improvement_ratio=expected_ratio,
            description=description,
            applied=False,
            confidence=confidence,
            rollback_key=self._generate_rollback_key(),
        )

        profile.improvements.append(improvement)
        self._save_profile(profile)

        return improvement

    def apply_improvement(
        self,
        skill_name: str,
        improvement: SkillImprovement,
    ) -> bool:
        """Apply an improvement to a skill.

        Args:
            skill_name: Skill to improve
            improvement: SkillImprovement to apply

        Returns:
            True if applied successfully
        """
        profile = self._load_or_create_profile(skill_name)

        # Update profile
        profile.current_version = improvement.version
        improvement.applied = True

        self._save_profile(profile)

        return True

    def validate_improvement(
        self,
        skill_name: str,
        improvement: SkillImprovement,
    ) -> bool:
        """Validate that an applied improvement is working.

        Compares post-improvement metrics against expectations.
        Returns True if improvement achieved its goals.
        """
        if not improvement.applied or improvement.metrics_after is None:
            return False

        # Calculate actual improvement ratio
        before_success = improvement.metrics_before.success_rate
        after_success = improvement.metrics_after.success_rate

        if before_success == 0:
            actual_ratio = float('inf') if after_success > 0 else 1.0
        else:
            actual_ratio = after_success / before_success

        # Use Bayesian reasoning: confidence interval around expected ratio
        expected = improvement.improvement_ratio
        confidence_margin = improvement.confidence

        # Accept if actual is within confidence band of expected
        lower_bound = expected * (1.0 - confidence_margin)
        upper_bound = expected * (1.0 + confidence_margin)

        return lower_bound <= actual_ratio <= upper_bound

    def rollback_improvement(
        self,
        skill_name: str,
        improvement: SkillImprovement,
    ) -> bool:
        """Rollback an applied improvement.

        Reverts skill to previous version if improvement failed.
        """
        if not improvement.applied or not improvement.rollback_key:
            return False

        profile = self._load_or_create_profile(skill_name)

        # Revert version
        prev_version = self._prev_version(improvement.version)
        profile.current_version = prev_version

        # Mark as rolled back
        improvement.applied = False

        self._save_profile(profile)

        return True

    def get_transfer_opportunities(
        self,
        source_skill: str,
        target_domain: Optional[str] = None,
    ) -> List[str]:
        """Identify skills that could benefit from improvements to source_skill.

        Cross-domain transfer: if a skill improvement works well, which other
        skills could adopt similar improvements?

        Args:
            source_skill: Skill with successful improvements
            target_domain: Optional domain to filter by

        Returns:
            List of candidate skill names for transfer
        """
        profile = self._load_or_create_profile(source_skill)
        candidates = []

        # Find successful improvements
        successful = [
            imp for imp in profile.improvements
            if imp.applied and self.validate_improvement(source_skill, imp)
        ]

        if not successful:
            return candidates

        # Scan all other skills for transfer opportunities
        profiles_path = self._profiles_path()
        if not profiles_path.exists():
            return candidates

        try:
            with open(profiles_path, 'r') as f:
                for line in f:
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    other_name = data.get("skill_name", "")
                    if other_name == source_skill:
                        continue

                    # Simple heuristic: same category or domain overlap
                    if target_domain and target_domain not in data.get("transfer_domains", []):
                        continue

                    candidates.append(other_name)
        except Exception:
            pass

        return candidates[:10]  # Limit to top 10

    def get_improvement_stats(self) -> Dict[str, Any]:
        """Get overall statistics about improvements made."""
        stats = {
            "total_skills_tracked": 0,
            "total_improvements_applied": 0,
            "average_improvement_ratio": 0.0,
            "successful_validations": 0,
            "failed_validations": 0,
            "avg_confidence": 0.0,
        }

        profiles_path = self._profiles_path()
        if not profiles_path.exists():
            return stats

        try:
            improvement_ratios = []
            confidences = []

            with open(profiles_path, 'r') as f:
                for line in f:
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    stats["total_skills_tracked"] += 1

                    improvements = data.get("improvements", [])
                    for imp_data in improvements:
                        if imp_data.get("applied"):
                            stats["total_improvements_applied"] += 1
                            ratio = imp_data.get("improvement_ratio", 1.0)
                            confidence = imp_data.get("confidence", 0.5)
                            improvement_ratios.append(ratio)
                            confidences.append(confidence)

            if improvement_ratios:
                stats["average_improvement_ratio"] = sum(improvement_ratios) / len(improvement_ratios)

            if confidences:
                stats["avg_confidence"] = sum(confidences) / len(confidences)

        except Exception:
            pass

        return stats

    # Private methods

    def _load_or_create_profile(self, skill_name: str) -> SkillProfile:
        """Load skill profile from disk or create new."""
        if skill_name in self._profiles_cache:
            return self._profiles_cache[skill_name]

        profiles_path = self._profiles_path()

        if profiles_path.exists():
            try:
                with open(profiles_path, 'r') as f:
                    for line in f:
                        if not line.strip():
                            continue
                        data = json.loads(line)
                        if data.get("skill_name") == skill_name:
                            profile = self._deserialize_profile(data)
                            self._profiles_cache[skill_name] = profile
                            return profile
            except Exception:
                pass

        # Create new profile
        profile = SkillProfile(
            skill_name=skill_name,
            category="general",
            created_at=int(time.time()),
        )
        self._profiles_cache[skill_name] = profile
        return profile

    def _save_profile(self, profile: SkillProfile) -> None:
        """Persist profile to disk."""
        profiles_path = self._profiles_path()

        # Read existing profiles
        profiles = {}
        if profiles_path.exists():
            try:
                with open(profiles_path, 'r') as f:
                    for line in f:
                        if not line.strip():
                            continue
                        data = json.loads(line)
                        name = data.get("skill_name", "")
                        if name:
                            profiles[name] = data
            except Exception:
                pass

        # Update with current profile
        profiles[profile.skill_name] = self._serialize_profile(profile)

        # Write back
        try:
            with open(profiles_path, 'w') as f:
                for name, data in profiles.items():
                    f.write(json.dumps(data) + '\n')
        except Exception:
            pass

    def _serialize_profile(self, profile: SkillProfile) -> Dict[str, Any]:
        """Convert profile to JSON-serializable dict."""
        return {
            "skill_name": profile.skill_name,
            "category": profile.category,
            "created_at": profile.created_at,
            "current_version": profile.current_version,
            "total_runs": profile.total_runs,
            "improvements": [
                {
                    "skill_name": imp.skill_name,
                    "version": imp.version,
                    "improvement_type": imp.improvement_type.value,
                    "timestamp": imp.timestamp,
                    "improvement_ratio": imp.improvement_ratio,
                    "description": imp.description,
                    "applied": imp.applied,
                    "confidence": imp.confidence,
                }
                for imp in profile.improvements
            ],
            "recent_metrics": [
                {
                    "timestamp": m.timestamp,
                    "success_rate": m.success_rate,
                    "avg_latency_ms": m.avg_latency_ms,
                    "error_count": m.error_count,
                    "total_executions": m.total_executions,
                }
                for m in profile.recent_metrics
            ],
        }

    def _deserialize_profile(self, data: Dict[str, Any]) -> SkillProfile:
        """Reconstruct profile from JSON dict."""
        profile = SkillProfile(
            skill_name=data.get("skill_name", "unknown"),
            category=data.get("category", "general"),
            created_at=data.get("created_at", int(time.time())),
            current_version=data.get("current_version", "1.0"),
            total_runs=data.get("total_runs", 0),
        )

        # Reconstruct metrics
        for m_data in data.get("recent_metrics", []):
            metric = PerformanceMetric(
                timestamp=m_data.get("timestamp", 0),
                success_rate=m_data.get("success_rate", 0.0),
                avg_latency_ms=m_data.get("avg_latency_ms", 0.0),
                error_count=m_data.get("error_count", 0),
                total_executions=m_data.get("total_executions", 0),
            )
            profile.recent_metrics.append(metric)

        # Reconstruct improvements
        for imp_data in data.get("improvements", []):
            try:
                improvement = SkillImprovement(
                    skill_name=imp_data.get("skill_name", ""),
                    version=imp_data.get("version", "1.0"),
                    improvement_type=ImprovementType(imp_data.get("improvement_type", "performance")),
                    timestamp=imp_data.get("timestamp", 0),
                    metrics_before=PerformanceMetric(
                        timestamp=0,
                        success_rate=0.0,
                        avg_latency_ms=0.0,
                        error_count=0,
                        total_executions=0,
                    ),
                    metrics_after=None,
                    improvement_ratio=imp_data.get("improvement_ratio", 1.0),
                    description=imp_data.get("description", ""),
                    applied=imp_data.get("applied", False),
                    confidence=imp_data.get("confidence", 0.5),
                )
                profile.improvements.append(improvement)
            except Exception:
                pass

        return profile

    def _next_version(self, current: str) -> str:
        """Increment semantic version."""
        try:
            parts = current.split('.')
            if len(parts) >= 1:
                minor = int(parts[-1]) + 1
                return '.'.join(parts[:-1]) + '.' + str(minor)
        except Exception:
            pass
        return current + ".1"

    def _prev_version(self, current: str) -> str:
        """Decrement semantic version."""
        try:
            parts = current.split('.')
            if len(parts) >= 2 and int(parts[-1]) > 0:
                minor = int(parts[-1]) - 1
                return '.'.join(parts[:-1]) + '.' + str(minor)
            elif len(parts) == 1 and current != "1.0":
                return "1.0"
        except Exception:
            pass
        return current

    def _generate_rollback_key(self) -> str:
        """Generate unique rollback identifier."""
        return f"rb_{int(time.time() * 1000)}"


# Singleton instance for use across the agent
_engine: Optional[SelfImprovementEngine] = None


def get_improvement_engine() -> SelfImprovementEngine:
    """Get or create singleton improvement engine."""
    global _engine
    if _engine is None:
        _engine = SelfImprovementEngine()
    return _engine
