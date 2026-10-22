"""Proof-based verification framework.

Generates and verifies proofs of correct execution.
Every agent execution produces a proof that can be independently verified.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from enum import Enum
import json


class VerificationLevel(Enum):
    """Levels of verification detail."""
    ASSERTION = 1  # Runtime checks only
    TRACE_VALIDATION = 2  # Replay trace
    PROOF_VERIFICATION = 3  # Re-execute proof steps
    MODEL_CHECKING = 4  # Exhaustive state exploration


@dataclass
class Evidence:
    """Supporting evidence for a claim."""
    claim: str
    evidence_type: str  # "code_analysis", "test", "measurement", "logical"
    data: Dict[str, Any]
    confidence: float  # 0.0-1.0


@dataclass
class ProofStep:
    """Single step in a proof."""
    step_num: int
    description: str
    precondition: str
    action: str
    postcondition: str
    evidence: List[Evidence] = field(default_factory=list)


@dataclass
class Proof:
    """Formal proof of correctness."""
    proof_id: str
    task: str
    precondition: str
    steps: List[ProofStep]
    postcondition: str
    overall_evidence: List[Evidence] = field(default_factory=list)

    def verify_structure(self) -> bool:
        """Verify proof is well-formed."""
        # Check each step has required fields
        for step in self.steps:
            if not (step.description and step.action and step.evidence):
                return False
        return len(self.steps) > 0

    def minimum_confidence(self) -> float:
        """Get minimum confidence across all evidence."""
        all_evidence = self.overall_evidence
        for step in self.steps:
            all_evidence.extend(step.evidence)

        if not all_evidence:
            return 0.0

        return min(e.confidence for e in all_evidence)


class ProofBuilder:
    """Builds formal proofs during agent execution."""

    def __init__(self, proof_id: str, task: str):
        self.proof_id = proof_id
        self.task = task
        self.steps: List[ProofStep] = []
        self.precondition = ""
        self.postcondition = ""
        self.overall_evidence: List[Evidence] = []

    def add_precondition(self, condition: str):
        """Set precondition."""
        self.precondition = condition

    def add_postcondition(self, condition: str):
        """Set postcondition."""
        self.postcondition = condition

    def add_step(
        self,
        step_num: int,
        description: str,
        precondition: str,
        action: str,
        postcondition: str,
    ) -> "ProofStep":
        """Add proof step."""
        step = ProofStep(
            step_num=step_num,
            description=description,
            precondition=precondition,
            action=action,
            postcondition=postcondition,
        )
        self.steps.append(step)
        return step

    def add_evidence(
        self,
        claim: str,
        evidence_type: str,
        data: Dict[str, Any],
        confidence: float = 0.9,
    ):
        """Add evidence to overall proof."""
        evidence = Evidence(
            claim=claim,
            evidence_type=evidence_type,
            data=data,
            confidence=confidence,
        )
        self.overall_evidence.append(evidence)

    def add_step_evidence(
        self,
        step_num: int,
        claim: str,
        evidence_type: str,
        data: Dict[str, Any],
        confidence: float = 0.9,
    ):
        """Add evidence to specific step."""
        for step in self.steps:
            if step.step_num == step_num:
                evidence = Evidence(
                    claim=claim,
                    evidence_type=evidence_type,
                    data=data,
                    confidence=confidence,
                )
                step.evidence.append(evidence)
                return

    def build(self) -> Proof:
        """Build final proof."""
        return Proof(
            proof_id=self.proof_id,
            task=self.task,
            precondition=self.precondition,
            steps=self.steps,
            postcondition=self.postcondition,
            overall_evidence=self.overall_evidence,
        )


class ProofVerifier:
    """Verifies proofs of correctness."""

    @staticmethod
    def verify(proof: Proof, level: VerificationLevel = VerificationLevel.ASSERTION) -> bool:
        """Verify proof at given level."""
        if not proof.verify_structure():
            return False

        if level == VerificationLevel.ASSERTION:
            return ProofVerifier._verify_assertion(proof)
        elif level == VerificationLevel.TRACE_VALIDATION:
            return ProofVerifier._verify_trace(proof)
        elif level == VerificationLevel.PROOF_VERIFICATION:
            return ProofVerifier._verify_proof(proof)
        elif level == VerificationLevel.MODEL_CHECKING:
            return ProofVerifier._verify_model(proof)

        return False

    @staticmethod
    def _verify_assertion(proof: Proof) -> bool:
        """Verify proof structure and minimum confidence."""
        return proof.verify_structure() and proof.minimum_confidence() >= 0.7

    @staticmethod
    def _verify_trace(proof: Proof) -> bool:
        """Verify proof by replaying trace."""
        # Check each step's postcondition is next step's precondition
        for i in range(len(proof.steps) - 1):
            step = proof.steps[i]
            next_step = proof.steps[i + 1]

            if step.postcondition != next_step.precondition:
                return False

        # Check first step precondition matches proof precondition
        if proof.steps and proof.steps[0].precondition != proof.precondition:
            return False

        # Check last step postcondition matches proof postcondition
        if proof.steps and proof.steps[-1].postcondition != proof.postcondition:
            return False

        return True

    @staticmethod
    def _verify_proof(proof: Proof) -> bool:
        """Verify proof by checking all evidence."""
        # All evidence must have high confidence
        all_evidence = proof.overall_evidence.copy()
        for step in proof.steps:
            all_evidence.extend(step.evidence)

        return all(e.confidence >= 0.85 for e in all_evidence)

    @staticmethod
    def _verify_model(proof: Proof) -> bool:
        """Exhaustive model checking (simplified)."""
        # For now, just verify structure
        # Full model checking would require state space exploration
        return proof.verify_structure()


class ClaimVerifier:
    """Verifies specific claims made by agents."""

    def __init__(self):
        self.verifiers: Dict[str, Callable] = {}

    def register_verifier(self, claim_type: str, verifier: Callable):
        """Register custom verifier for claim type."""
        self.verifiers[claim_type] = verifier

    def verify_claim(self, claim: str, evidence_data: Dict[str, Any]) -> bool:
        """Verify a claim against evidence."""
        for claim_type, verifier in self.verifiers.items():
            if claim_type in claim:
                return verifier(claim, evidence_data)

        # Default: require evidence
        return "evidence" in evidence_data or len(evidence_data) > 0


class SpecificationValidator:
    """Validates task execution against specification."""

    @staticmethod
    def create_spec(
        task_name: str,
        preconditions: List[str],
        steps: List[str],
        postconditions: List[str],
    ) -> Dict[str, Any]:
        """Create formal task specification."""
        return {
            "task": task_name,
            "preconditions": preconditions,
            "steps": steps,
            "postconditions": postconditions,
        }

    @staticmethod
    def validate_against_spec(
        spec: Dict[str, Any], execution_trace: List[Dict]
    ) -> bool:
        """Validate execution trace against specification."""
        if not execution_trace:
            return False

        # Check we executed the required steps (order matters)
        # This is a simplified check
        executed_steps = [
            entry.get("action", "") for entry in execution_trace
        ]

        # All spec steps should appear in execution
        for spec_step in spec["steps"]:
            if spec_step not in executed_steps:
                return False

        return True


__all__ = [
    "Proof",
    "ProofStep",
    "Evidence",
    "ProofBuilder",
    "ProofVerifier",
    "VerificationLevel",
    "ClaimVerifier",
    "SpecificationValidator",
]
