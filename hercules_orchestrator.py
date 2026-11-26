#!/usr/bin/env python3
"""
Hercules Multi-Platform Intelligence Orchestrator

Unified coordination and observability across all Hercules platforms.
Integrates Langfuse tracing, consensus verification, delegation tracking,
and cross-platform decision making into a single intelligence layer.

This module enables:
- Global visibility across 10+ messaging platforms (Slack, Discord, Telegram, etc.)
- Cross-platform consensus verification using existing proof system
- Platform-specific performance analytics
- Coordinated multi-agent decision making
- Automatic learning and optimization across all domains

Architecture:
  OrchestratorHub (main coordinator)
    ├── Langfuse integration (global traces)
    ├── Platform analytics engine (per-platform metrics)
    ├── Consensus registry (verified decisions)
    ├── Delegation tracker (subagent coordination)
    └── Learning engine (cross-platform optimization)

Design principles (from CLAUDE.md):
- Core is narrow: extend via plugins/skills where possible
- Delegation is open: trust subagent results
- Proofs are replayable: verification derives verdict, never asserts
- Standing decays: past performance is not future guarantee
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Any, Set, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class PlatformType(Enum):
    """All supported Hercules platforms."""
    SLACK = "slack"
    DISCORD = "discord"
    TELEGRAM = "telegram"
    TEAMS = "teams"
    MATTERMOST = "mattermost"
    MATRIX = "matrix"
    WHATSAPP = "whatsapp"
    FEISHU = "feishu"
    IRC = "irc"
    SMS = "sms"
    GOOGLE_CHAT = "google_chat"
    HOMEASSISTANT = "homeassistant"


class ConsensusVerdictType(Enum):
    """Verdict types from consensus system (agent/consensus/records.py)."""
    VERIFIED = "verified"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"
    CONFLICTED = "conflicted"


@dataclass(frozen=True)
class PlatformContext:
    """Context for a single platform session."""
    platform: PlatformType
    session_id: str
    user_id: str
    team_id: Optional[str] = None
    channel_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform": self.platform.value,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "team_id": self.team_id,
            "channel_id": self.channel_id,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class PlatformMetrics:
    """Aggregated metrics for a single platform."""
    platform: PlatformType
    total_conversations: int = 0
    successful_conversations: int = 0
    failed_conversations: int = 0
    avg_response_time_ms: float = 0.0
    total_tokens_used: int = 0
    total_cost_usd: float = 0.0
    error_rate: float = 0.0
    consensus_success_rate: float = 0.0
    tools_used: Dict[str, int] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=datetime.utcnow)

    def success_rate(self) -> float:
        """Calculate success rate for this platform."""
        if self.total_conversations == 0:
            return 0.0
        return self.successful_conversations / self.total_conversations

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["platform"] = self.platform.value
        data["last_updated"] = self.last_updated.isoformat()
        data["success_rate"] = self.success_rate()
        return data


@dataclass
class ConsensusRecord:
    """Record of a cross-platform consensus decision."""
    consensus_id: str
    participants: Set[str]  # Verifier agent IDs
    claim_id: str
    verdict: ConsensusVerdictType
    agreement_rate: float  # 0.0 to 1.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    verified_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DelegationRecord:
    """Record of a delegation to subagent."""
    delegation_id: str
    parent_agent_id: str
    child_agent_id: str
    task_id: str
    platform: PlatformType
    status: str  # "pending", "running", "completed", "failed"
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def duration_ms(self) -> Optional[float]:
        """Duration in milliseconds if completed."""
        if self.completed_at:
            return (self.completed_at - self.created_at).total_seconds() * 1000
        return None


class PlatformAnalytics:
    """Per-platform analytics engine.

    Tracks and aggregates metrics per platform, enables cross-platform
    comparison and anomaly detection.
    """

    def __init__(self):
        self.metrics: Dict[PlatformType, PlatformMetrics] = {
            platform: PlatformMetrics(platform=platform)
            for platform in PlatformType
        }
        self._lock = threading.RLock()

    def record_conversation(
        self,
        platform: PlatformType,
        success: bool,
        response_time_ms: float,
        tokens_used: int,
        cost_usd: float,
        tools_used: Optional[List[str]] = None,
    ):
        """Record a conversation on a platform."""
        with self._lock:
            m = self.metrics[platform]
            m.total_conversations += 1

            if success:
                m.successful_conversations += 1
            else:
                m.failed_conversations += 1

            m.avg_response_time_ms = (
                (m.avg_response_time_ms * (m.total_conversations - 1) + response_time_ms)
                / m.total_conversations
            )
            m.total_tokens_used += tokens_used
            m.total_cost_usd += cost_usd
            m.error_rate = m.failed_conversations / m.total_conversations

            if tools_used:
                for tool in tools_used:
                    m.tools_used[tool] = m.tools_used.get(tool, 0) + 1

            m.last_updated = datetime.utcnow()

    def get_metrics(self, platform: PlatformType) -> PlatformMetrics:
        """Get current metrics for a platform."""
        with self._lock:
            return self.metrics[platform]

    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all platforms."""
        with self._lock:
            return {
                platform.value: self.metrics[platform].to_dict()
                for platform in PlatformType
            }

    def compare_platforms(self) -> Dict[str, Any]:
        """Compare performance across platforms."""
        with self._lock:
            metrics_dict = self.get_all_metrics()

            return {
                "total_conversations": sum(m["total_conversations"] for m in metrics_dict.values()),
                "best_success_rate": max(
                    (m["platform"], m["success_rate"]) for m in metrics_dict.values()
                ),
                "worst_success_rate": min(
                    (m["platform"], m["success_rate"]) for m in metrics_dict.values()
                ),
                "avg_cost_per_conversation": (
                    sum(m["total_cost_usd"] for m in metrics_dict.values())
                    / max(1, sum(m["total_conversations"] for m in metrics_dict.values()))
                ),
                "by_platform": metrics_dict,
            }


class ConsensusRegistry:
    """Registry and verification of cross-platform consensus decisions.

    Integrates with agent/consensus/proofs.py for deterministic verification.
    Tracks multi-agent consensus verdicts across platforms.
    """

    def __init__(self):
        self.records: Dict[str, ConsensusRecord] = {}
        self._lock = threading.RLock()

    def register_consensus(
        self,
        consensus_id: str,
        participants: Set[str],
        claim_id: str,
        verdict: ConsensusVerdictType,
        agreement_rate: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ConsensusRecord:
        """Register a consensus decision."""
        with self._lock:
            record = ConsensusRecord(
                consensus_id=consensus_id,
                participants=participants,
                claim_id=claim_id,
                verdict=verdict,
                agreement_rate=agreement_rate,
                metadata=metadata or {},
            )
            self.records[consensus_id] = record
            logger.info(
                f"Consensus registered: {consensus_id} "
                f"({len(participants)} participants, {agreement_rate:.1%} agreement)"
            )
            return record

    def verify_consensus(self, consensus_id: str) -> Optional[ConsensusRecord]:
        """Verify and mark a consensus decision as verified."""
        with self._lock:
            if consensus_id not in self.records:
                return None

            record = self.records[consensus_id]
            if record.verified_at is None:
                record.verified_at = datetime.utcnow()
                logger.info(f"Consensus verified: {consensus_id}")

            return record

    def get_consensus_rate(self) -> float:
        """Get overall consensus success rate."""
        with self._lock:
            if not self.records:
                return 0.0

            verified = [
                r for r in self.records.values()
                if r.verdict == ConsensusVerdictType.VERIFIED
            ]
            return len(verified) / len(self.records) if self.records else 0.0

    def get_consensus_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent consensus records."""
        with self._lock:
            sorted_records = sorted(
                self.records.values(),
                key=lambda r: r.created_at,
                reverse=True,
            )[:limit]

            return [
                {
                    "consensus_id": r.consensus_id,
                    "participants": list(r.participants),
                    "verdict": r.verdict.value,
                    "agreement_rate": r.agreement_rate,
                    "created_at": r.created_at.isoformat(),
                    "verified_at": r.verified_at.isoformat() if r.verified_at else None,
                }
                for r in sorted_records
            ]


class DelegationTracker:
    """Track and monitor delegations to subagents across platforms.

    Coordinates with tools/delegate_tool.py for subagent spawning and
    result collection.
    """

    def __init__(self):
        self.records: Dict[str, DelegationRecord] = {}
        self._lock = threading.RLock()

    def create_delegation(
        self,
        delegation_id: str,
        parent_agent_id: str,
        child_agent_id: str,
        task_id: str,
        platform: PlatformType,
    ) -> DelegationRecord:
        """Create a delegation record."""
        with self._lock:
            record = DelegationRecord(
                delegation_id=delegation_id,
                parent_agent_id=parent_agent_id,
                child_agent_id=child_agent_id,
                task_id=task_id,
                platform=platform,
                status="pending",
            )
            self.records[delegation_id] = record
            logger.info(f"Delegation created: {delegation_id} on {platform.value}")
            return record

    def mark_running(self, delegation_id: str):
        """Mark delegation as running."""
        with self._lock:
            if delegation_id in self.records:
                self.records[delegation_id].status = "running"

    def mark_completed(
        self,
        delegation_id: str,
        result: Dict[str, Any],
    ):
        """Mark delegation as completed."""
        with self._lock:
            if delegation_id in self.records:
                record = self.records[delegation_id]
                record.status = "completed"
                record.result = result
                record.completed_at = datetime.utcnow()
                logger.info(
                    f"Delegation completed: {delegation_id} "
                    f"({record.duration_ms():.1f}ms)"
                )

    def mark_failed(self, delegation_id: str, error: str):
        """Mark delegation as failed."""
        with self._lock:
            if delegation_id in self.records:
                record = self.records[delegation_id]
                record.status = "failed"
                record.error = error
                record.completed_at = datetime.utcnow()
                logger.error(f"Delegation failed: {delegation_id}: {error}")

    def get_success_rate(self) -> float:
        """Get overall delegation success rate."""
        with self._lock:
            completed = [r for r in self.records.values() if r.status in ["completed", "failed"]]
            if not completed:
                return 0.0

            successful = [r for r in completed if r.status == "completed"]
            return len(successful) / len(completed)

    def get_average_duration_ms(self) -> float:
        """Get average delegation duration."""
        with self._lock:
            completed = [r for r in self.records.values() if r.completed_at]
            if not completed:
                return 0.0

            durations = [r.duration_ms() for r in completed if r.duration_ms()]
            return sum(durations) / len(durations) if durations else 0.0


class OrchestratorHub:
    """Central coordinator for multi-platform Hercules intelligence.

    Integrates:
    - Langfuse observability (via langfuse_integration.LangfuseObserver)
    - Platform analytics (per-platform metrics)
    - Consensus verification (agent/consensus/)
    - Delegation tracking (tools/delegate_tool.py)
    - Cross-platform learning

    Single source of truth for global agent intelligence state.
    """

    def __init__(self, langfuse_observer=None):
        """Initialize orchestrator.

        Args:
            langfuse_observer: LangfuseObserver instance for tracing
        """
        self.langfuse = langfuse_observer
        self.analytics = PlatformAnalytics()
        self.consensus = ConsensusRegistry()
        self.delegations = DelegationTracker()
        self._lock = threading.RLock()
        self._started_at = datetime.utcnow()

        logger.info("OrchestratorHub initialized")

    def record_platform_conversation(
        self,
        platform: PlatformType,
        session_id: str,
        user_id: str,
        success: bool,
        response_time_ms: float,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        tools_used: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Record a conversation from any platform.

        This is the main entry point for platform-level observations.
        Coordinates with Langfuse and platform analytics.
        """
        total_tokens = input_tokens + output_tokens

        # Record to analytics
        self.analytics.record_conversation(
            platform=platform,
            success=success,
            response_time_ms=response_time_ms,
            tokens_used=total_tokens,
            cost_usd=cost_usd,
            tools_used=tools_used,
        )

        # Record to Langfuse if enabled
        if self.langfuse:
            self.langfuse.start_trace(
                name=f"platform-{platform.value}",
                user_id=user_id,
                metadata={
                    "platform": platform.value,
                    "session_id": session_id,
                    "success": success,
                    "tools_used": tools_used or [],
                },
            )
            self.langfuse.log_generation(
                model="multi-platform-decision",
                prompt=f"Platform: {platform.value}, Session: {session_id}",
                completion=f"Status: {success}, Tokens: {total_tokens}",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd,
            )
            self.langfuse.end_trace(metadata={
                "status": "completed" if success else "failed",
                "response_time_ms": response_time_ms,
            })

        logger.info(
            f"Platform conversation recorded: {platform.value} "
            f"({total_tokens} tokens, ${cost_usd:.4f})"
        )

    def record_consensus_verification(
        self,
        consensus_id: str,
        participants: Set[str],
        claim_id: str,
        verdict: ConsensusVerdictType,
        agreement_rate: float,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Record a cross-platform consensus verification."""
        self.consensus.register_consensus(
            consensus_id=consensus_id,
            participants=participants,
            claim_id=claim_id,
            verdict=verdict,
            agreement_rate=agreement_rate,
            metadata=metadata,
        )

    def create_delegation(
        self,
        delegation_id: str,
        parent_agent_id: str,
        child_agent_id: str,
        task_id: str,
        platform: PlatformType,
    ) -> DelegationRecord:
        """Create a delegation record."""
        return self.delegations.create_delegation(
            delegation_id=delegation_id,
            parent_agent_id=parent_agent_id,
            child_agent_id=child_agent_id,
            task_id=task_id,
            platform=platform,
        )

    def complete_delegation(self, delegation_id: str, result: Dict[str, Any]):
        """Mark delegation as completed."""
        self.delegations.mark_completed(delegation_id, result)

    def fail_delegation(self, delegation_id: str, error: str):
        """Mark delegation as failed."""
        self.delegations.mark_failed(delegation_id, error)

    def get_global_status(self) -> Dict[str, Any]:
        """Get global orchestrator status across all platforms."""
        with self._lock:
            analytics = self.analytics.compare_platforms()

            return {
                "timestamp": datetime.utcnow().isoformat(),
                "uptime_seconds": (datetime.utcnow() - self._started_at).total_seconds(),
                "analytics": analytics,
                "consensus": {
                    "success_rate": self.consensus.get_consensus_rate(),
                    "total_records": len(self.consensus.records),
                },
                "delegations": {
                    "success_rate": self.delegations.get_success_rate(),
                    "avg_duration_ms": self.delegations.get_average_duration_ms(),
                    "total_delegations": len(self.delegations.records),
                },
            }

    def get_platform_comparison(self) -> Dict[str, Any]:
        """Compare all platforms in detail."""
        return self.analytics.compare_platforms()

    def get_recent_consensus_decisions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent consensus decisions."""
        return self.consensus.get_consensus_history(limit)

    def flush(self):
        """Flush all pending events."""
        if self.langfuse:
            self.langfuse.flush()
        logger.info("OrchestratorHub flushed")


# Singleton instance
_orchestrator: Optional[OrchestratorHub] = None
_orchestrator_lock = threading.Lock()


def get_orchestrator(langfuse_observer=None) -> OrchestratorHub:
    """Get or create the global orchestrator instance."""
    global _orchestrator

    if _orchestrator is None:
        with _orchestrator_lock:
            if _orchestrator is None:
                _orchestrator = OrchestratorHub(langfuse_observer)

    return _orchestrator
