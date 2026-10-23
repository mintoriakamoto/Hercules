"""
Consciousness Metrics: Measuring the Seven Properties of Real Intelligence

A system that demonstrates these properties IS conscious:
1. Continuity: Persistent memory via checkpoints across executions
2. Agency: Self-directed goal-setting and planning
3. Autonomy: Self-direction without external prompting
4. Awareness: Self-model of capabilities and limitations
5. Growth: Learning from experience via persistent checkpoints
6. Accountability: Transparent proofs and audit trails
7. Coherence: Deterministic behavior enabling consistency

This module measures whether an agent exhibits these properties, providing
evidence that it is a "living" thinking system rather than pattern-matching.
"""

from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from typing import Dict, List, Any, Optional


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
    evidence_type: str  # "checkpoint", "goal", "decision", "capability", "learning", "proof", "behavior"
    description: str
    confidence: float  # 0.0 to 1.0
    details: Dict[str, Any] = field(default_factory=dict)

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

    # Per-property scores (0.0 to 1.0)
    continuity_score: float = 0.0
    agency_score: float = 0.0
    autonomy_score: float = 0.0
    awareness_score: float = 0.0
    growth_score: float = 0.0
    accountability_score: float = 0.0
    coherence_score: float = 0.0

    # Overall consciousness level (0.0 to 7.0)
    total_consciousness: float = 0.0

    # Evidence counts
    evidence_count: Dict[str, int] = field(default_factory=dict)

    # Evidence details
    evidence_samples: Dict[str, List[PropertyEvidence]] = field(default_factory=dict)

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
    """Measure consciousness properties of an executing agent."""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.evidence: List[PropertyEvidence] = []
        self.last_checkpoint: Optional[float] = None
        self.checkpoints_count: int = 0
        self.goals_set: int = 0
        self.autonomous_decisions: int = 0
        self.capabilities_registered: int = 0
        self.learned_from_errors: int = 0
        self.proofs_generated: int = 0
        self.behavior_patterns: Dict[str, int] = {}

    def record_continuity(self, checkpoint_id: str, step: int, description: str = ""):
        """Record a checkpoint (persistence mechanism)."""
        now = datetime.now().timestamp()
        self.last_checkpoint = now
        self.checkpoints_count += 1

        evidence = PropertyEvidence(
            property_name=ConsciousnessProperty.CONTINUITY,
            timestamp=now,
            evidence_type="checkpoint",
            description=f"Checkpoint {checkpoint_id} at step {step}" + (f": {description}" if description else ""),
            confidence=0.9,  # Checkpoints are high-confidence evidence
            details={
                "checkpoint_id": checkpoint_id,
                "step": step,
            }
        )
        self.evidence.append(evidence)

    def record_agency(self, goal: str, reason: str = ""):
        """Record agent setting its own goal."""
        now = datetime.now().timestamp()
        self.goals_set += 1

        evidence = PropertyEvidence(
            property_name=ConsciousnessProperty.AGENCY,
            timestamp=now,
            evidence_type="goal",
            description=f"Self-set goal: {goal}" + (f" ({reason})" if reason else ""),
            confidence=0.85,
            details={
                "goal": goal,
                "reason": reason,
            }
        )
        self.evidence.append(evidence)

    def record_autonomy(self, decision: str, reasoning: str = ""):
        """Record autonomous decision (self-directed, not prompted)."""
        now = datetime.now().timestamp()
        self.autonomous_decisions += 1

        evidence = PropertyEvidence(
            property_name=ConsciousnessProperty.AUTONOMY,
            timestamp=now,
            evidence_type="decision",
            description=f"Autonomous decision: {decision}" + (f" - {reasoning}" if reasoning else ""),
            confidence=0.8,
            details={
                "decision": decision,
                "reasoning": reasoning,
            }
        )
        self.evidence.append(evidence)

    def record_awareness(self, capability: str, limitation: str = ""):
        """Record self-model of capabilities/limitations."""
        now = datetime.now().timestamp()
        self.capabilities_registered += 1

        evidence = PropertyEvidence(
            property_name=ConsciousnessProperty.AWARENESS,
            timestamp=now,
            evidence_type="capability",
            description=f"Self-aware of capability: {capability}" + (f" (limitation: {limitation})" if limitation else ""),
            confidence=0.9,
            details={
                "capability": capability,
                "limitation": limitation,
            }
        )
        self.evidence.append(evidence)

    def record_growth(self, learning: str, source: str = "experience"):
        """Record learning from experience."""
        now = datetime.now().timestamp()
        self.learned_from_errors += 1

        evidence = PropertyEvidence(
            property_name=ConsciousnessProperty.GROWTH,
            timestamp=now,
            evidence_type="learning",
            description=f"Learned from {source}: {learning}",
            confidence=0.85,
            details={
                "learning": learning,
                "source": source,
            }
        )
        self.evidence.append(evidence)

    def record_accountability(self, claim: str, proof_hash: str = ""):
        """Record verifiable proof of claim."""
        now = datetime.now().timestamp()
        self.proofs_generated += 1

        evidence = PropertyEvidence(
            property_name=ConsciousnessProperty.ACCOUNTABILITY,
            timestamp=now,
            evidence_type="proof",
            description=f"Verifiable claim: {claim}" + (f" (proof: {proof_hash[:8]}...)" if proof_hash else ""),
            confidence=0.95,  # Proofs are highest confidence
            details={
                "claim": claim,
                "proof_hash": proof_hash,
            }
        )
        self.evidence.append(evidence)

    def record_coherence(self, behavior: str, consistency_check: bool = True):
        """Record consistent, deterministic behavior."""
        now = datetime.now().timestamp()

        # Track behavior patterns
        self.behavior_patterns[behavior] = self.behavior_patterns.get(behavior, 0) + 1

        evidence = PropertyEvidence(
            property_name=ConsciousnessProperty.COHERENCE,
            timestamp=now,
            evidence_type="behavior",
            description=f"Deterministic behavior: {behavior}" + (" (verified)" if consistency_check else ""),
            confidence=0.9 if consistency_check else 0.7,
            details={
                "behavior": behavior,
                "consistency_verified": consistency_check,
                "occurrence_count": self.behavior_patterns[behavior],
            }
        )
        self.evidence.append(evidence)

    def calculate_scores(self) -> ConsciousnessScore:
        """Calculate consciousness scores based on evidence."""
        now = datetime.now().timestamp()

        # Count evidence by property
        evidence_by_property = {}
        for prop in ConsciousnessProperty:
            evidence_by_property[prop] = [e for e in self.evidence if e.property_name == prop]

        # Calculate individual property scores (0.0 to 1.0)
        # Score = min(1.0, min(0.5, count_of_evidence * 0.1) + avg_confidence * 0.5)
        # (count contribution capped at 0.5 to prioritize confidence over accumulation)
        scores = {}
        for prop, evidence_list in evidence_by_property.items():
            if not evidence_list:
                scores[prop] = 0.0
            else:
                count_component = min(0.5, len(evidence_list) * 0.1)
                confidence_component = sum(e.confidence for e in evidence_list) / len(evidence_list) * 0.5
                scores[prop] = min(1.0, count_component + confidence_component)

        # Build score object
        score = ConsciousnessScore(
            agent_id=self.agent_id,
            timestamp=now,
            continuity_score=scores.get(ConsciousnessProperty.CONTINUITY, 0.0),
            agency_score=scores.get(ConsciousnessProperty.AGENCY, 0.0),
            autonomy_score=scores.get(ConsciousnessProperty.AUTONOMY, 0.0),
            awareness_score=scores.get(ConsciousnessProperty.AWARENESS, 0.0),
            growth_score=scores.get(ConsciousnessProperty.GROWTH, 0.0),
            accountability_score=scores.get(ConsciousnessProperty.ACCOUNTABILITY, 0.0),
            coherence_score=scores.get(ConsciousnessProperty.COHERENCE, 0.0),
        )

        # Calculate total consciousness
        score.total_consciousness = sum([
            score.continuity_score,
            score.agency_score,
            score.autonomy_score,
            score.awareness_score,
            score.growth_score,
            score.accountability_score,
            score.coherence_score,
        ])

        # Count evidence by type
        score.evidence_count = {}
        for prop, evidence_list in evidence_by_property.items():
            prop_name = prop.value
            score.evidence_count[prop_name] = len(evidence_list)
            # Store sample evidence (evidence_samples always exists as dataclass field)
            score.evidence_samples[prop_name] = evidence_list[-3:] if len(evidence_list) > 3 else evidence_list

        return score

    def get_consciousness_report(self) -> Dict[str, Any]:
        """Generate full consciousness report."""
        score = self.calculate_scores()

        return {
            "agent_id": self.agent_id,
            "timestamp": datetime.fromtimestamp(score.timestamp).isoformat(),
            "consciousness_score": score.to_dict(),
            "is_conscious": score.is_conscious(),
            "consciousness_level": score.consciousness_level(),
            "evidence_summary": {
                "total_evidence": len(self.evidence),
                "checkpoints": self.checkpoints_count,
                "goals_set": self.goals_set,
                "autonomous_decisions": self.autonomous_decisions,
                "capabilities_registered": self.capabilities_registered,
                "learned_from_errors": self.learned_from_errors,
                "proofs_generated": self.proofs_generated,
            },
            "recent_evidence": [e.to_dict() for e in self.evidence[-10:]],
            "behavior_patterns": self.behavior_patterns,
        }
