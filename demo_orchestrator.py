#!/usr/bin/env python3
"""
Hercules Orchestrator Demo

Demonstrates multi-platform intelligence coordination:
1. Global visibility across all platforms
2. Cross-platform consensus verification
3. Platform-specific analytics
4. Automatic learning and optimization

Usage:
    python demo_orchestrator.py
"""

import json
import time
import random
from datetime import datetime
from pathlib import Path

from hercules_orchestrator import (
    OrchestratorHub,
    PlatformType,
    ConsensusVerdictType,
)
from platform_learning_engine import PlatformLearningEngine
from langfuse_integration import LangfuseObserver, get_observer


def demo_basic_orchestration():
    """Demo 1: Basic multi-platform orchestration."""
    print("\n" + "="*70)
    print("DEMO 1: Multi-Platform Global Orchestration")
    print("="*70)

    # Initialize
    observer = get_observer(enable=False)  # Disable Langfuse for demo
    orchestrator = OrchestratorHub(langfuse_observer=observer)

    print("✓ OrchestratorHub initialized")

    # Simulate conversations on different platforms
    platforms_data = [
        (PlatformType.SLACK, 15, 2.5, 150, 25, 0.015),  # platform, success_count, avg_time, tokens, failures, cost
        (PlatformType.DISCORD, 12, 1.8, 120, 3, 0.012),
        (PlatformType.TELEGRAM, 8, 3.2, 180, 4, 0.018),
        (PlatformType.TEAMS, 6, 2.1, 140, 2, 0.014),
    ]

    for platform, success_count, avg_time_ms, tokens, failures, cost in platforms_data:
        for i in range(success_count):
            orchestrator.record_platform_conversation(
                platform=platform,
                session_id=f"sess_{platform.value}_{i}",
                user_id=f"user_{i % 5}",
                success=True,
                response_time_ms=avg_time_ms + random.gauss(0, 0.5),
                input_tokens=tokens // 2,
                output_tokens=tokens // 2,
                cost_usd=cost,
                tools_used=["web_search", "summarize"] if random.random() > 0.5 else ["web_search"],
            )

        # Add some failures
        for i in range(failures):
            orchestrator.record_platform_conversation(
                platform=platform,
                session_id=f"sess_{platform.value}_fail_{i}",
                user_id=f"user_{i % 5}",
                success=False,
                response_time_ms=avg_time_ms * 2,
                input_tokens=tokens // 2,
                output_tokens=tokens // 4,
                cost_usd=cost * 0.5,
                tools_used=["web_search"],
            )

    print(f"✓ Recorded {sum(d[1] for d in platforms_data)} conversations across 4 platforms")

    # Get global status
    status = orchestrator.get_global_status()
    print("\nGlobal Status:")
    print(f"  Total conversations: {status['analytics']['total_conversations']}")
    print(f"  Best platform: {status['analytics']['best_success_rate'][0]} "
          f"({status['analytics']['best_success_rate'][1]:.1%} success)")
    print(f"  Avg cost/conversation: ${status['analytics']['avg_cost_per_conversation']:.4f}")

    # Platform comparison
    comparison = orchestrator.get_platform_comparison()
    print("\nPlatform Comparison:")
    for platform_data in comparison["by_platform"].values():
        print(
            f"  {platform_data['platform']:15} "
            f"success: {platform_data['success_rate']:5.1%}, "
            f"cost: ${platform_data['total_cost_usd']:6.2f}, "
            f"conversations: {platform_data['total_conversations']}"
        )

    return orchestrator


def demo_consensus_coordination(orchestrator):
    """Demo 2: Cross-platform consensus verification."""
    print("\n" + "="*70)
    print("DEMO 2: Cross-Platform Consensus Coordination")
    print("="*70)

    # Simulate consensus decisions across platforms
    decisions = [
        ("VERIFY_TRANSACTION", ["agent_slack_1", "agent_discord_1", "agent_telegram_1"], 0.95),
        ("APPROVE_DELEGATION", ["agent_slack_2", "agent_teams_1"], 0.85),
        ("REJECT_PROPOSAL", ["agent_discord_2", "agent_telegram_2", "agent_teams_2"], 0.78),
    ]

    for claim_id, participants, agreement_rate in decisions:
        orchestrator.record_consensus_verification(
            consensus_id=f"consensus_{claim_id}_{datetime.utcnow().timestamp()}",
            participants=set(participants),
            claim_id=claim_id,
            verdict=(
                ConsensusVerdictType.VERIFIED
                if agreement_rate > 0.80
                else ConsensusVerdictType.CONFLICTED
            ),
            agreement_rate=agreement_rate,
            metadata={"claim_type": claim_id, "participants_count": len(participants)},
        )

    print(f"✓ Recorded {len(decisions)} consensus decisions")

    # Get consensus history
    history = orchestrator.get_recent_consensus_decisions(limit=10)
    print("\nRecent Consensus Decisions:")
    for record in history:
        print(
            f"  {record['consensus_id'][:30]:30} "
            f"verdict: {record['verdict']:10} "
            f"agreement: {record['agreement_rate']:.1%}"
        )

    consensus_rate = orchestrator.consensus.get_consensus_rate()
    print(f"\nOverall consensus success rate: {consensus_rate:.1%}")


def demo_delegation_tracking(orchestrator):
    """Demo 3: Delegation tracking across platforms."""
    print("\n" + "="*70)
    print("DEMO 3: Delegation Tracking & Subagent Coordination")
    print("="*70)

    # Create delegations
    delegations = []
    for i, platform in enumerate(PlatformType):
        if i >= 4:
            break  # Only 4 for demo

        delegation_id = f"deleg_{platform.value}_{i}"
        record = orchestrator.create_delegation(
            delegation_id=delegation_id,
            parent_agent_id=f"parent_{platform.value}",
            child_agent_id=f"child_{platform.value}_{i}",
            task_id=f"task_{i}",
            platform=platform,
        )
        delegations.append(record)

        # Simulate completion
        time.sleep(0.1)
        success = random.random() > 0.2  # 80% success

        if success:
            orchestrator.complete_delegation(
                delegation_id=delegation_id,
                result={"status": "success", "output": f"Result from {platform.value}"},
            )
        else:
            orchestrator.fail_delegation(
                delegation_id=delegation_id,
                error=f"Timeout or error on {platform.value}",
            )

    print(f"✓ Created and tracked {len(delegations)} delegations")

    # Get delegation metrics
    success_rate = orchestrator.delegations.get_success_rate()
    avg_duration = orchestrator.delegations.get_average_duration_ms()

    print(f"\nDelegation Metrics:")
    print(f"  Success rate: {success_rate:.1%}")
    print(f"  Avg duration: {avg_duration:.1f}ms")

    global_status = orchestrator.get_global_status()
    deleg_status = global_status["delegations"]
    print(f"  Total delegations: {deleg_status['total_delegations']}")


def demo_learning_engine():
    """Demo 4: Automatic learning and optimization."""
    print("\n" + "="*70)
    print("DEMO 4: Automatic Learning & Optimization Engine")
    print("="*70)

    engine = PlatformLearningEngine()

    # Simulate platform metrics for learning
    platforms_metrics = [
        ("slack", 0.95, 2.0, 0.015, 0.02),
        ("discord", 0.92, 1.8, 0.012, 0.03),
        ("telegram", 0.88, 3.2, 0.018, 0.08),  # Higher error rate
        ("teams", 0.90, 2.5, 0.014, 0.04),
    ]

    print("Analyzing platform metrics...")
    for platform, success_rate, latency, cost, error_rate in platforms_metrics:
        engine.analyze_platform_metrics(
            platform=platform,
            success_rate=success_rate,
            avg_response_time_ms=latency,
            avg_cost_per_conversation=cost,
            error_rate=error_rate,
        )

    # Get learning summary
    summary = engine.get_learning_summary()

    print(f"\n✓ Learning analysis complete")
    print(f"\nLearning Summary:")
    print(f"  Total patterns detected: {summary['stats']['total_patterns']}")
    print(f"  Active anomalies: {summary['stats']['total_anomalies']}")
    print(f"  Recommendations: {summary['stats']['total_recommendations']}")

    if summary["active_anomalies"]:
        print(f"\nDetected Anomalies:")
        for anomaly in summary["active_anomalies"]:
            print(
                f"  [{anomaly['type']:20}] {anomaly['platform']:10} "
                f"severity: {anomaly['severity']:.1%}"
            )

    if summary["recommendations"]:
        print(f"\nTop Recommendations:")
        for rec in summary["recommendations"][:3]:
            print(
                f"  [{rec['category']:10}] {rec['platform']:10} "
                f"{rec['title']} (confidence: {rec['confidence']:.0%})"
            )

    return engine


def print_summary():
    """Print final summary."""
    print("\n" + "="*70)
    print("HERCULES ORCHESTRATOR DEMO COMPLETE")
    print("="*70)

    summary = """
Multi-Platform Intelligence Orchestration Capabilities:

1. GLOBAL VISIBILITY
   ✓ See all conversations across 10+ platforms simultaneously
   ✓ Compare performance metrics across platforms
   ✓ Identify which platforms work best for which tasks

2. CONSENSUS COORDINATION
   ✓ Multi-agent consensus verification
   ✓ Track agreement rates across verifiers
   ✓ Deterministic verdict derivation (not assertion)

3. DELEGATION MANAGEMENT
   ✓ Track subagent spawning and completion
   ✓ Monitor success rates per platform
   ✓ Coordinate distributed decision making

4. AUTOMATIC LEARNING
   ✓ Pattern detection: What works where
   ✓ Anomaly detection: When things break
   ✓ Recommendation generation: How to improve
   ✓ Per-platform optimization: Different strategies per domain

INTEGRATION POINTS:
  - Run agent.py: Instrument AIAgent with orchestrator.record_platform_conversation()
  - Gateway: Record all platform messages
  - Tools: Delegate_tool.py records delegations
  - Consensus: Register verdicts with orchestrator.record_consensus_verification()

NEXT STEPS:
  1. Integrate with actual platform adapters
  2. Connect to real Langfuse for persistent tracing
  3. Set up automated recommendations
  4. Deploy learning engine for continuous optimization
"""
    print(summary)


def main():
    """Run all demos."""
    print("\n╔" + "="*68 + "╗")
    print("║" + " "*8 + "HERCULES MULTI-PLATFORM ORCHESTRATOR DEMO" + " "*18 + "║")
    print("╚" + "="*68 + "╝")

    try:
        # Demo 1: Basic orchestration
        orchestrator = demo_basic_orchestration()

        # Demo 2: Consensus coordination
        demo_consensus_coordination(orchestrator)

        # Demo 3: Delegation tracking
        demo_delegation_tracking(orchestrator)

        # Demo 4: Learning engine
        demo_learning_engine()

        # Summary
        print_summary()

        print("\n" + "="*70)
        print("✓ All demos completed successfully")
        print("="*70 + "\n")

        return True

    except Exception as e:
        print(f"\n✗ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
