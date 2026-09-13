"""Content trust and approval boundary system.

Ensures all external content (web fetches, browser content, user uploads)
goes through explicit approval gates with content-hash based tracking.

This closes the bypass where web content could reach execution planning
without the same approval gates that protect agent-supplied commands.

Design:
  - All external content tagged as UNTRUSTED
  - Content-hash based approval caching (changes re-trigger gate)
  - Audit trail for every approval
  - Explicit content source tracking
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ContentSource(Enum):
    """Source of content requiring approval."""

    # Internal
    AGENT_COMMAND = "agent.command"      # Command from model/agent
    CONFIG_FILE = "config.file"          # From configuration

    # External
    WEB_FETCH = "web.fetch"              # HTTP fetch result
    WEB_BROWSER = "web.browser"          # Browser content
    USER_UPLOAD = "user.upload"          # User-uploaded file
    CLI_STDIN = "cli.stdin"              # User input from terminal

    def requires_approval(self) -> bool:
        """Check if content from this source needs approval."""
        # Only internal sources skip approval
        return self not in [ContentSource.CONFIG_FILE]


@dataclass
class ContentApproval:
    """Record of an approved content action."""

    action_type: str  # "execute", "install", "configure", etc.
    content_source: ContentSource
    content_hash: str  # SHA256 of content
    timestamp: float
    user_approved: bool = False
    user_email: Optional[str] = None
    approval_notes: Optional[str] = None

    def is_still_valid_for(self, current_content: str) -> bool:
        """Check if approval applies to current content.

        Content must match original hash for approval to apply.
        """
        current_hash = self._hash_content(current_content)
        return current_hash == self.content_hash

    @staticmethod
    def _hash_content(content: str) -> str:
        """Hash content for comparison."""
        return hashlib.sha256(content.encode()).hexdigest()

    def to_dict(self) -> Dict:
        """Serialize to dictionary."""
        return {
            "action_type": self.action_type,
            "content_source": self.content_source.value,
            "content_hash": self.content_hash,
            "timestamp": self.timestamp,
            "user_approved": self.user_approved,
            "user_email": self.user_email,
            "approval_notes": self.approval_notes,
        }


class ApprovalDenied(Exception):
    """Raised when content approval is denied."""
    def __init__(self, reason: str, content_source: ContentSource):
        self.reason = reason
        self.content_source = content_source
        super().__init__(f"Approval denied: {reason} (source: {content_source.value})")


class ContentApprovalManager:
    """Manages content approvals with hash-based invalidation.

    Features:
      - Explicit content source tracking
      - Hash-based approval caching
      - Audit trail
      - Replay attack prevention (hash changes re-trigger approval)
    """

    def __init__(self, approval_log_path: Optional[Path] = None):
        """Initialize approval manager.

        Args:
            approval_log_path: Path to save approval audit trail
        """
        self.approval_log_path = approval_log_path
        self.approvals: Dict[str, List[ContentApproval]] = {}
        self.pending_approvals: Dict[str, ContentApproval] = {}

        if approval_log_path and approval_log_path.exists():
            self._load_approvals(approval_log_path)

    def _load_approvals(self, path: Path) -> None:
        """Load approval history from log file."""
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            for key, approvals in data.items():
                self.approvals[key] = [
                    ContentApproval(
                        action_type=a["action_type"],
                        content_source=ContentSource(a["content_source"]),
                        content_hash=a["content_hash"],
                        timestamp=a["timestamp"],
                        user_approved=a.get("user_approved", False),
                        user_email=a.get("user_email"),
                        approval_notes=a.get("approval_notes"),
                    )
                    for a in approvals
                ]
            logger.info("Loaded %d approval records", sum(len(v) for v in self.approvals.values()))
        except Exception as e:
            logger.error("Failed to load approvals from %s: %s", path, e)

    def request_approval(
        self,
        action_type: str,
        content: str,
        content_source: ContentSource,
        approval_notes: Optional[str] = None,
    ) -> ContentApproval:
        """Request approval for an action with content.

        Args:
            action_type: Type of action (execute, install, etc.)
            content: Content being approved
            content_source: Source of content
            approval_notes: Optional notes about the approval

        Returns:
            ContentApproval record (may need user approval)

        Raises:
            ApprovalDenied: If content previously denied
        """
        content_hash = self._hash_content(content)
        key = f"{action_type}:{content_source.value}"

        # Check if this content was previously approved
        if key in self.approvals:
            for prev_approval in self.approvals[key]:
                if prev_approval.is_still_valid_for(content):
                    logger.info(
                        "Reusing previous approval for %s (hash: %s)",
                        action_type,
                        content_hash[:8],
                    )
                    return prev_approval

        # Check if this content was previously denied
        if key in self.pending_approvals:
            prev = self.pending_approvals[key]
            if not prev.user_approved and prev.is_still_valid_for(content):
                raise ApprovalDenied(
                    f"Content previously denied (hash: {content_hash[:8]})",
                    content_source
                )

        # Create new approval record (pending user review)
        approval = ContentApproval(
            action_type=action_type,
            content_source=content_source,
            content_hash=content_hash,
            timestamp=time.time(),
            user_approved=False,
            approval_notes=approval_notes,
        )

        self.pending_approvals[key] = approval

        logger.warning(
            "Approval needed for %s from %s (hash: %s)",
            action_type,
            content_source.value,
            content_hash[:8],
        )

        return approval

    def approve(
        self,
        approval: ContentApproval,
        user_email: Optional[str] = None,
    ) -> None:
        """Mark an approval as user-approved.

        Args:
            approval: Approval to mark as approved
            user_email: User who approved
        """
        approval.user_approved = True
        approval.user_email = user_email
        approval.timestamp = time.time()

        key = f"{approval.action_type}:{approval.content_source.value}"

        if key not in self.approvals:
            self.approvals[key] = []

        self.approvals[key].append(approval)
        self.pending_approvals.pop(key, None)

        logger.info(
            "Approval granted for %s from %s by %s (hash: %s)",
            approval.action_type,
            approval.content_source.value,
            user_email or "system",
            approval.content_hash[:8],
        )

        self._save_approvals()

    def deny(self, approval: ContentApproval) -> None:
        """Mark an approval as denied."""
        key = f"{approval.action_type}:{approval.content_source.value}"
        self.pending_approvals[key] = approval
        logger.warning(
            "Approval denied for %s from %s (hash: %s)",
            approval.action_type,
            approval.content_source.value,
            approval.content_hash[:8],
        )

    def get_pending_approvals(self) -> List[ContentApproval]:
        """Get all pending approvals awaiting user review."""
        return list(self.pending_approvals.values())

    def get_approval_history(self, limit: int = 100) -> List[ContentApproval]:
        """Get recent approval history."""
        all_approvals = []
        for approvals in self.approvals.values():
            all_approvals.extend(approvals)

        # Sort by timestamp, newest first
        all_approvals.sort(key=lambda a: a.timestamp, reverse=True)
        return all_approvals[:limit]

    def _save_approvals(self) -> None:
        """Save approval audit trail to file."""
        if not self.approval_log_path:
            return

        try:
            data = {
                key: [a.to_dict() for a in approvals]
                for key, approvals in self.approvals.items()
            }
            with open(self.approval_log_path, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug("Saved approvals to %s", self.approval_log_path)
        except Exception as e:
            logger.error("Failed to save approvals: %s", e)

    @staticmethod
    def _hash_content(content: str) -> str:
        """Hash content for comparison."""
        return hashlib.sha256(content.encode()).hexdigest()


# Module-level instance for backwards compatibility
_global_manager: Optional[ContentApprovalManager] = None


def get_approval_manager() -> ContentApprovalManager:
    """Get or create global approval manager."""
    global _global_manager
    if _global_manager is None:
        _global_manager = ContentApprovalManager()
    return _global_manager


def set_approval_manager(manager: ContentApprovalManager) -> None:
    """Set global approval manager."""
    global _global_manager
    _global_manager = manager
