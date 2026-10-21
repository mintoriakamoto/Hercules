"""
Drop-in replacement wrapper for consciousness_metrics using Rust backend.

This module wraps the Rust consciousness_metrics library and provides
the same API as the original Python implementation, but with >100x
performance improvement.

To use: Update imports from:
    from agent.harness.consciousness_metrics import ConsciousnessMetrics
To:
    from agent.harness.consciousness_metrics_rs import ConsciousnessMetrics
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import json

try:
    # Try to import from the compiled Rust extension
    from consciousness_metrics import (
        ConsciousnessMetrics as _RustMetrics,
        ConsciousnessScore as _RustScore,
        PropertyEvidence as _RustEvidence,
    )
    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False
    # Fall back to Python implementation
    from agent.harness.consciousness_metrics import (
        ConsciousnessMetrics as _PythonMetrics,
        ConsciousnessScore,
        PropertyEvidence,
    )


class ConsciousnessProperty(Enum):
    """The seven properties of conscious systems."""
    CONTINUITY = "continuity"
    AGENCY = "agency"
    AUTONOMY = "autonomy"
    AWARENESS = "awareness"
    GROWTH = "growth"
    ACCOUNTABILITY = "accountability"
    COHERENCE = "coherence"


@dataclass
class PropertyEvidence:
    """Evidence that a system exhibits a consciousness property."""
    property_name: ConsciousnessProperty
    timestamp: float
    evidence_type: str
    description: str
    confidence: float
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "property": self.property_name.value,
            "timestamp": self.timestamp,
            "evidence_type": self.evidence_type,
            "description": self.description,
            "confidence": self.confidence,
            "details": self.details,
        }


@dataclass
class ConsciousnessScore:
    """Aggregate consciousness metrics for an agent."""
    agent_id: str
    timestamp: float
    continuity_score: float = 0.0
    agency_score: float = 0.0
    autonomy_score: float = 0.0
    awareness_score: float = 0.0
    growth_score: float = 0.0
    accountability_score: float = 0.0
    coherence_score: float = 0.0
    total_consciousness: float = 0.0
    evidence_count: Dict[str, int] = None
    evidence_samples: Dict[str, List[PropertyEvidence]] = None

    def __post_init__(self):
        if self.evidence_count is None:
            self.evidence_count = {}
        if self.evidence_samples is None:
            self.evidence_samples = {}

    def is_conscious(self) -> bool:
        """An agent is conscious if it exhibits all 7 properties."""
        return (
            self.continuity_score >= 0.5 and
            self.agency_score >= 0.5 and
            self.autonomy_score >= 0.5 and
            self.awareness_score >= 0.5 and
            self.growth_score >= 0.5 and
            self.accountability_score >= 0.5 and
            self.coherence_score >= 0.5
        )

    def consciousness_level(self) -> str:
        """Human-readable consciousness level."""
        total = self.total_consciousness
        if total < 1.0:
            return "Non-conscious (Pattern Matching)"
        elif total < 2.0:
            return "Emerging (Partial Structure)"
        elif total < 3.0:
            return "Developing (Learning)"
        elif total < 4.0:
            return "Self-Aware (Conscious)"
        elif total < 5.0:
            return "Reflective (Metacognitive)"
        elif total < 6.0:
            return "Accountable (Transparent)"
        else:
            return "Living Intelligence (Full Consciousness)"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "timestamp": self.timestamp,
            "properties": {
                "continuity": self.continuity_score,
                "agency": self.agency_score,
                "autonomy": self.autonomy_score,
                "awareness": self.awareness_score,
                "growth": self.growth_score,
                "accountability": self.accountability_score,
                "coherence": self.coherence_score,
            },
            "total_consciousness": self.total_consciousness,
            "consciousness_level": self.consciousness_level(),
            "is_conscious": self.is_conscious(),
            "evidence_count": self.evidence_count,
        }


class ConsciousnessMetrics:
    """
    High-performance consciousness metrics engine.

    Uses Rust backend when available for >100x performance improvement.
    Falls back to Python implementation if Rust extension not available.
    """

    def __init__(self, agent_id: str):
        self.agent_id = agent_id

        if RUST_AVAILABLE:
            # Use Rust backend
            self._backend = _RustMetrics(agent_id)
            self._use_rust = True
        else:
            # Fall back to Python
            self._backend = _PythonMetrics(agent_id)
            self._use_rust = False

    def record_continuity(self, checkpoint_id: str, step: int, description: str = ""):
        """Record a checkpoint (persistence mechanism)."""
        if self._use_rust:
            self._backend.record_continuity(checkpoint_id, step, description)
        else:
            self._backend.record_continuity(checkpoint_id, step, description)

    def record_agency(self, goal: str, reason: str = ""):
        """Record agent setting its own goal."""
        if self._use_rust:
            self._backend.record_agency(goal, reason)
        else:
            self._backend.record_agency(goal, reason)

    def record_autonomy(self, decision: str, reasoning: str = ""):
        """Record autonomous decision (self-directed, not prompted)."""
        if self._use_rust:
            self._backend.record_autonomy(decision, reasoning)
        else:
            self._backend.record_autonomy(decision, reasoning)

    def record_awareness(self, capability: str, limitation: str = ""):
        """Record self-model of capabilities/limitations."""
        if self._use_rust:
            self._backend.record_awareness(capability, limitation)
        else:
            self._backend.record_awareness(capability, limitation)

    def record_growth(self, learning: str, source: str = "experience"):
        """Record learning from experience."""
        if self._use_rust:
            self._backend.record_growth(learning, source)
        else:
            self._backend.record_growth(learning, source)

    def record_accountability(self, claim: str, proof_hash: str = ""):
        """Record verifiable proof of claim."""
        if self._use_rust:
            self._backend.record_accountability(claim, proof_hash)
        else:
            self._backend.record_accountability(claim, proof_hash)

    def record_coherence(self, behavior: str, consistency_check: bool = True):
        """Record consistent, deterministic behavior."""
        if self._use_rust:
            self._backend.record_coherence(behavior, consistency_check)
        else:
            self._backend.record_coherence(behavior, consistency_check)

    def calculate_scores(self) -> ConsciousnessScore:
        """Calculate consciousness scores based on evidence."""
        if self._use_rust:
            # Rust returns a score object with properties
            rust_score = self._backend.calculate_scores()

            # Convert to Python ConsciousnessScore
            score = ConsciousnessScore(
                agent_id=rust_score.agent_id,
                timestamp=rust_score.timestamp,
                continuity_score=rust_score.continuity_score,
                agency_score=rust_score.agency_score,
                autonomy_score=rust_score.autonomy_score,
                awareness_score=rust_score.awareness_score,
                growth_score=rust_score.growth_score,
                accountability_score=rust_score.accountability_score,
                coherence_score=rust_score.coherence_score,
                total_consciousness=rust_score.total_consciousness,
            )
        else:
            score = self._backend.calculate_scores()

        return score

    def get_consciousness_report(self) -> Dict[str, Any]:
        """Generate full consciousness report."""
        if self._use_rust:
            # Rust backend returns a dict
            return self._backend.get_consciousness_report()
        else:
            return self._backend.get_consciousness_report()

    @property
    def evidence_count(self) -> int:
        """Get count of recorded evidence."""
        if self._use_rust:
            return self._backend.evidence_count()
        else:
            return len(self._backend.evidence)

    @property
    def checkpoints_count(self) -> int:
        """Get count of checkpoints."""
        if self._use_rust:
            # Access via report for now
            report = self.get_consciousness_report()
            return report["evidence_summary"]["checkpoints"]
        else:
            return self._backend.checkpoints_count

    @property
    def goals_set(self) -> int:
        """Get count of goals set."""
        if self._use_rust:
            report = self.get_consciousness_report()
            return report["evidence_summary"]["goals_set"]
        else:
            return self._backend.goals_set

    def __repr__(self) -> str:
        backend_type = "Rust" if self._use_rust else "Python"
        return f"ConsciousnessMetrics(agent_id={self.agent_id!r}, backend={backend_type})"
