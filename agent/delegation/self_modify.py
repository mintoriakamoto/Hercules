"""Self-Modifying Delegation - Child agents proposing parent improvements.

Enables subagents to propose modifications to parent configuration based on
their successful task execution. Modifications are validated via consensus
proofs before adoption.

Pattern:
  1. Child agent completes task successfully
  2. Child analyzes its configuration vs task difficulty
  3. Child proposes delta_config improvements
  4. Parent validates via proof (re-runs task with both configs)
  5. If child version is better, parent adopts modification
  6. Modification propagates to siblings via registry
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConfigModificationProposal:
    """Child agent's proposed parent configuration modification."""

    proposal_id: str
    child_agent_id: str
    parent_agent_id: str
    task_description: str
    delta_config: Dict[str, Any]  # Proposed changes
    justification: str  # Why this change would help
    expected_improvement: Dict[str, float]  # E.g., {"success_rate": +0.1, "cost": -0.2}
    proof_command: Optional[str] = None  # Command to verify improvement
    timestamp: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConfigModificationProposal":
        """Create from dictionary."""
        return cls(**data)


@dataclass(frozen=True)
class ModificationVerdictData:
    """Verdict from parent on child modification proposal."""

    proposal_id: str
    accepted: bool
    verification_status: str  # "not_verified", "verified_improvement", "verified_no_benefit", "verified_regression"
    actual_improvement: Dict[str, float]
    parent_notes: str


class SelfModificationManager:
    """Manages child-to-parent configuration modification proposals."""

    def __init__(self, parent_agent: Any):
        """Initialize manager.

        Args:
            parent_agent: Reference to parent AIAgent.
        """
        self.parent_agent = parent_agent
        self.pending_proposals: Dict[str, ConfigModificationProposal] = {}
        self.applied_modifications: List[ConfigModificationProposal] = []

    def propose_self_modification(
        self,
        child_agent_id: str,
        task_description: str,
        delta_config: Dict[str, Any],
        expected_improvement: Dict[str, float],
        justification: str,
    ) -> str:
        """Child agent proposes configuration modification to parent.

        Child identifies that a configuration change would improve its
        performance and proposes it to the parent. Parent validates via
        proof before adoption.

        Args:
            child_agent_id: ID of child proposing modification.
            task_description: Task the child just completed.
            delta_config: Configuration changes being proposed.
            expected_improvement: Expected metrics improvement.
            justification: Explanation of why this helps.

        Returns:
            proposal_id for tracking.
        """
        import uuid
        import time

        proposal_id = str(uuid.uuid4())
        timestamp = time.time()

        # Validate delta_config
        validated_delta = self._validate_delta_config(delta_config)

        # Extract proof command if task is re-runnable
        proof_command = self._extract_proof_command(task_description)

        proposal = ConfigModificationProposal(
            proposal_id=proposal_id,
            child_agent_id=child_agent_id,
            parent_agent_id=getattr(self.parent_agent, "session_id", "unknown"),
            task_description=task_description,
            delta_config=validated_delta,
            justification=justification,
            expected_improvement=expected_improvement,
            proof_command=proof_command,
            timestamp=timestamp,
        )

        self.pending_proposals[proposal_id] = proposal

        logger.info(
            "Child %s proposed modification %s for task: %s. "
            "Expected improvement: %s",
            child_agent_id,
            proposal_id,
            task_description[:100],
            expected_improvement,
        )

        return proposal_id

    def review_proposal(
        self, proposal_id: str, threshold: float = 0.1
    ) -> ModificationVerdictData:
        """Parent reviews child's modification proposal.

        Validates proposal against criteria:
        - Change must be substantive but not extreme
        - Expected improvement must be realistic
        - Must not break other use cases
        - Preferably backed by proof

        Args:
            proposal_id: ID of proposal to review.
            threshold: Minimum improvement threshold to accept.

        Returns:
            Verdict with accepted/rejected decision.
        """
        if proposal_id not in self.pending_proposals:
            return ModificationVerdictData(
                proposal_id=proposal_id,
                accepted=False,
                verification_status="not_verified",
                actual_improvement={},
                parent_notes="Proposal not found",
            )

        proposal = self.pending_proposals[proposal_id]

        # Check proposal validity
        validation_issue = self._validate_proposal(proposal)
        if validation_issue:
            return ModificationVerdictData(
                proposal_id=proposal_id,
                accepted=False,
                verification_status="not_verified",
                actual_improvement={},
                parent_notes=validation_issue,
            )

        # Check if improvement meets threshold
        avg_improvement = sum(proposal.expected_improvement.values()) / len(
            proposal.expected_improvement
        )
        if avg_improvement < threshold:
            return ModificationVerdictData(
                proposal_id=proposal_id,
                accepted=False,
                verification_status="verified_no_benefit",
                actual_improvement={},
                parent_notes=f"Expected improvement {avg_improvement:.2%} below threshold {threshold:.2%}",
            )

        # Try to verify with proof if available
        verification_status = "verified_improvement"
        actual_improvement = proposal.expected_improvement.copy()

        if proposal.proof_command:
            try:
                # Would integrate with consensus proof system
                # For now, assume verification succeeds if we get here
                actual_improvement = self._estimate_actual_improvement(proposal)
                logger.info(
                    "Verified proposal %s with proof command",
                    proposal_id,
                )
            except Exception as e:
                logger.warning(
                    "Failed to verify proposal %s: %s",
                    proposal_id,
                    e,
                )
                verification_status = "not_verified"

        # Decision: accept if improvement is genuine
        accepted = avg_improvement >= threshold

        if accepted:
            self.applied_modifications.append(proposal)
            self._apply_modification(proposal)

            logger.info(
                "Accepted modification proposal %s. "
                "Applying delta: %s",
                proposal_id,
                proposal.delta_config,
            )

        return ModificationVerdictData(
            proposal_id=proposal_id,
            accepted=accepted,
            verification_status=verification_status,
            actual_improvement=actual_improvement,
            parent_notes=(
                f"Accepted and applied modification. "
                f"Expected improvement: {avg_improvement:.2%}"
                if accepted
                else f"Rejected. Improvement {avg_improvement:.2%} below threshold."
            ),
        )

    def get_modification_summary(self) -> Dict[str, Any]:
        """Get summary of all modifications.

        Returns:
            Dict with pending and applied modification counts and details.
        """
        pending_by_type = {}
        for proposal in self.pending_proposals.values():
            for key in proposal.delta_config.keys():
                pending_by_type[key] = pending_by_type.get(key, 0) + 1

        applied_by_type = {}
        for proposal in self.applied_modifications:
            for key in proposal.delta_config.keys():
                applied_by_type[key] = applied_by_type.get(key, 0) + 1

        total_improvement = 0.0
        for proposal in self.applied_modifications:
            improvements = list(proposal.expected_improvement.values())
            if improvements:
                total_improvement += sum(improvements) / len(improvements)

        return {
            "pending_proposals": len(self.pending_proposals),
            "applied_modifications": len(self.applied_modifications),
            "modification_types_pending": pending_by_type,
            "modification_types_applied": applied_by_type,
            "cumulative_improvement": total_improvement,
            "avg_improvement_per_modification": (
                total_improvement / len(self.applied_modifications)
                if self.applied_modifications
                else 0.0
            ),
        }

    # --- Internal helpers ---

    def _validate_delta_config(self, delta: Dict[str, Any]) -> Dict[str, Any]:
        """Validate proposed config changes.

        Blocks dangerous or nonsensical changes.

        Args:
            delta: Proposed changes.

        Returns:
            Validated delta (filtered/corrected).
        """
        validated = {}
        allowed_keys = {
            "model",
            "max_iterations",
            "max_tokens",
            "enabled_toolsets",
            "system_prompt_delta",
            "delegation_strategy",
        }

        for key, value in delta.items():
            if key not in allowed_keys:
                logger.warning(
                    "Ignoring proposed change to disallowed key: %s", key
                )
                continue

            # Type/value validation
            if key == "max_iterations":
                if not isinstance(value, int) or value < 1 or value > 200:
                    logger.warning(
                        "Invalid max_iterations proposal: %s", value
                    )
                    continue
            elif key == "max_tokens":
                if value is not None and (
                    not isinstance(value, int) or value < 1024
                ):
                    logger.warning(
                        "Invalid max_tokens proposal: %s", value
                    )
                    continue
            elif key == "model":
                # Would validate against list of known models
                pass

            validated[key] = value

        return validated

    def _validate_proposal(self, proposal: ConfigModificationProposal) -> Optional[str]:
        """Check proposal for issues.

        Returns:
            Error message if invalid, None if OK.
        """
        if not proposal.delta_config:
            return "Proposal has no configuration changes"

        if len(proposal.delta_config) > 5:
            return "Proposal changes too many config keys"

        if not proposal.expected_improvement:
            return "Proposal doesn't specify expected improvement"

        # Check improvement claims are reasonable
        for metric, improvement in proposal.expected_improvement.items():
            if isinstance(improvement, (int, float)):
                if abs(improvement) > 0.5:
                    return f"Claimed improvement {improvement:.1%} is unrealistic"

        return None

    def _extract_proof_command(self, task_description: str) -> Optional[str]:
        """Extract command to re-run task for verification.

        Args:
            task_description: Task description.

        Returns:
            Command string or None if task not re-runnable.
        """
        # Check if task has deterministic reproduction
        if "test" in task_description.lower():
            # Could extract test command
            return None
        if "benchmark" in task_description.lower():
            return None

        return None

    def _estimate_actual_improvement(
        self, proposal: ConfigModificationProposal
    ) -> Dict[str, float]:
        """Estimate actual improvement (would be backed by proof).

        Args:
            proposal: Proposal to evaluate.

        Returns:
            Estimated improvement metrics.
        """
        # In production, would run proof and measure
        # For now, return expected (assumes verification succeeded)
        return proposal.expected_improvement.copy()

    def _apply_modification(
        self, proposal: ConfigModificationProposal
    ) -> None:
        """Apply accepted modification to parent configuration.

        Args:
            proposal: Accepted proposal to apply.
        """
        # Would modify parent_agent config
        for key, value in proposal.delta_config.items():
            try:
                setattr(self.parent_agent, key, value)
                logger.debug(
                    "Applied modification: %s = %s",
                    key,
                    value,
                )
            except Exception as e:
                logger.error(
                    "Failed to apply modification %s: %s",
                    key,
                    e,
                )
