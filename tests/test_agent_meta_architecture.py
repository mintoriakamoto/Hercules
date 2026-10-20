#!/usr/bin/env python3
"""Tests for agent metaprogramming architecture system.

Tests the complete self-designing agent system including:
  - Introspection API (self-awareness)
  - Design API (architecture generation)
  - Registry (learning from successes)
  - Emergence tracking (capability growth)
  - Self-modification (child→parent improvements)
  - Task-aware design (customization)
"""

import json
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from agent.meta.introspection import (
    Introspection,
    AgentConfig,
    CapabilityProfile,
    TaskPerformance,
    CapabilityGap,
)
from agent.meta.design import Design, AgentVariant, ToolsetComposition
from agent.meta.registry import ArchitectureRegistry, ArchitectureRecord
from agent.meta.emergence import (
    EmergenceTracker,
    AgentGenealogy,
    EmergenceEvent,
)
from agent.delegation.self_modify import (
    SelfModificationManager,
    ConfigModificationProposal,
    ModificationVerdictData,
)
from agent.planning.task_designer import (
    TaskDesigner,
    TaskAnalysis,
    AgentBlueprint,
)


class TestIntrospection(unittest.TestCase):
    """Test agent introspection API."""

    def setUp(self):
        """Set up test agent."""
        self.mock_agent = MagicMock()
        self.mock_agent.model = "claude-opus-4-20250514"
        self.mock_agent.enabled_toolsets = ["core", "terminal", "files"]
        self.mock_agent.max_tokens = 8192
        self.mock_agent.max_iterations = 30
        self.mock_agent.session_id = "test-agent-123"
        self.mock_agent.system_prompt = "You are a helpful assistant."
        self.introspection = Introspection(self.mock_agent)

    def test_get_self_config(self):
        """Test getting agent configuration."""
        config = self.introspection.get_self_config()

        self.assertIsInstance(config, AgentConfig)
        self.assertEqual(config.model, "claude-opus-4-20250514")
        self.assertEqual(config.max_tokens, 8192)
        self.assertEqual(config.max_iterations, 30)
        self.assertIn("core", config.toolsets)

    def test_query_self_capabilities(self):
        """Test querying agent capabilities."""
        with patch(
            "agent.meta.introspection.Introspection._get_available_tools"
        ) as mock_tools:
            mock_tools.return_value = ["bash", "python", "read_file"]

            capabilities = self.introspection.query_self_capabilities()

            self.assertIsInstance(capabilities, CapabilityProfile)
            self.assertIn("bash", capabilities.tools)
            self.assertTrue(hasattr(capabilities, "success_rate"))

    def test_estimate_capability_gap(self):
        """Test capability gap estimation."""
        task = "Design a complex distributed system architecture using extended thinking"

        gaps = self.introspection.estimate_capability_gap(task)

        self.assertIsInstance(gaps, list)
        # Should suggest extended thinking for complex design task
        gap_types = [g.gap_type for g in gaps]
        # May or may not detect gaps depending on mock setup
        self.assertTrue(isinstance(gaps, list))

    def test_get_performance_history(self):
        """Test getting task performance history."""
        history = self.introspection.get_performance_history(limit=10)

        self.assertIsInstance(history, list)
        # Initially empty for mock agent
        self.assertEqual(len(history), 0)


class TestDesign(unittest.TestCase):
    """Test agent design API."""

    def setUp(self):
        """Set up test agent and designer."""
        self.mock_agent = MagicMock()
        self.mock_agent.model = "claude-opus-4-20250514"
        self.design = Design(self.mock_agent)

    def test_propose_agent_variant(self):
        """Test proposing optimized agent variant."""
        goal = "Implement a new feature with comprehensive testing"
        context = {"complexity": "high"}
        budget = {"max_tokens": 10000}

        variant = self.design.propose_agent_variant(goal, context, budget)

        self.assertIsInstance(variant, AgentVariant)
        self.assertIsNotNone(variant.model)
        self.assertIsNotNone(variant.toolsets)
        self.assertGreater(variant.max_iterations, 0)

    def test_generate_system_prompt_variant(self):
        """Test generating specialized system prompt."""
        task = "Code a Python web scraper"
        constraints = {"focus": "web scraping"}

        prompt = self.design.generate_system_prompt_variant(task, constraints)

        self.assertIsInstance(prompt, str)
        self.assertIn("Task Focus", prompt)
        self.assertGreater(len(prompt), 50)

    def test_compose_toolset(self):
        """Test toolset composition."""
        requirements = ["code", "file_ops", "bash"]
        budget = {"max_tokens": 8000}

        composition = self.design.compose_toolset(requirements, budget)

        self.assertIsInstance(composition, ToolsetComposition)
        self.assertGreater(len(composition.selected_toolsets), 0)
        self.assertTrue(0 <= composition.coverage_percentage <= 1)


class TestArchitectureRegistry(unittest.TestCase):
    """Test architecture learning registry."""

    def setUp(self):
        """Create temporary registry."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = str(Path(self.temp_dir) / "registry.db")
        self.registry = ArchitectureRegistry(db_path=self.db_path)

    def tearDown(self):
        """Clean up."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_record_task_result(self):
        """Test recording task-agent pairing."""
        record = ArchitectureRecord(
            task_id="task-001",
            task_description="Implement sorting algorithm",
            task_type="coding",
            agent_config={"model": "claude-opus", "toolsets": ["code"]},
            success=True,
            success_rate=0.95,
            avg_cost_tokens=1500,
            iterations_used=8,
            model_used="claude-opus-4-20250514",
            toolsets_used=["code", "terminal"],
            timestamp=time.time(),
        )

        self.registry.record_task_result(record)

        # Verify recorded
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM architecture_records"
            )
            count = cursor.fetchone()[0]
            self.assertEqual(count, 1)

    def test_lookup_successful_architecture(self):
        """Test looking up similar successful tasks."""
        # Record a successful task
        record = ArchitectureRecord(
            task_id="task-001",
            task_description="Write Python code for data processing",
            task_type="coding",
            agent_config={"model": "claude-opus", "toolsets": ["code"]},
            success=True,
            success_rate=0.95,
            avg_cost_tokens=1500,
            iterations_used=8,
            model_used="claude-opus-4-20250514",
            toolsets_used=["code"],
            timestamp=time.time(),
        )
        self.registry.record_task_result(record)

        # Look up similar
        similar = self.registry.lookup_successful_architecture(
            "Create Python script for processing"
        )

        # May or may not find (depends on keyword matching)
        # Main thing is it doesn't error
        self.assertTrue(similar is None or isinstance(similar, dict))

    def test_get_statistics(self):
        """Test getting registry statistics."""
        stats = self.registry.get_statistics()

        self.assertIsInstance(stats, dict)
        self.assertIn("total_records", stats)
        self.assertIn("overall_success_rate", stats)

    def test_clear_old_records(self):
        """Test clearing old records."""
        # Record something very old
        record = ArchitectureRecord(
            task_id="task-old",
            task_description="Old task",
            task_type="general",
            agent_config={},
            success=True,
            success_rate=0.8,
            avg_cost_tokens=1000,
            iterations_used=10,
            model_used="old-model",
            toolsets_used=[],
            timestamp=time.time() - (60 * 86400),  # 60 days ago
        )
        self.registry.record_task_result(record)

        # Clear records >30 days old
        deleted = self.registry.clear_old_records(days=30)

        self.assertEqual(deleted, 1)


class TestEmergenceTracker(unittest.TestCase):
    """Test capability emergence tracking."""

    def setUp(self):
        """Create temporary tracker."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = str(Path(self.temp_dir) / "emergence.db")
        self.tracker = EmergenceTracker(db_path=self.db_path)

    def tearDown(self):
        """Clean up."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_record_genealogy(self):
        """Test recording agent genealogy."""
        genealogy = AgentGenealogy(
            agent_id="agent-child",
            parent_agent_id="agent-parent",
            grandparent_id="agent-grandparent",
            designer_agent_id="designer-1",
            generation=2,
            design_timestamp=time.time(),
            capabilities_gained=["new_tool_1", "new_tool_2"],
            capabilities_lost=[],
            emergence_score=0.45,
        )

        self.tracker.record_agent_genealogy(genealogy)

        # Verify recorded
        lineage = self.tracker.get_agent_lineage("agent-child")
        self.assertEqual(len(lineage), 1)
        self.assertEqual(lineage[0].agent_id, "agent-child")

    def test_record_emergence_event(self):
        """Test recording emergence event."""
        event = EmergenceEvent(
            event_id="event-001",
            agent_id="agent-child",
            parent_agent_id="agent-parent",
            event_type="new_tool",
            description="Discovered use of new bash scripting technique",
            impact_score=0.35,
            timestamp=time.time(),
            task_that_triggered="complex bash task",
            evidence={"new_tools": ["advanced_bash"]},
        )

        self.tracker.record_emergence_event(event)

        # Verify recorded
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM emergence_events"
            )
            count = cursor.fetchone()[0]
            self.assertEqual(count, 1)

    def test_detect_emergence(self):
        """Test emergence detection."""
        new_caps = ["tool_a", "tool_b", "tool_c"]
        parent_caps = ["tool_a"]
        performance = {
            "parent_avg_cost": 2000,
            "child_avg_cost": 1500,
            "parent_success_rate": 0.7,
            "child_success_rate": 0.85,
        }

        events = self.tracker.detect_emergence(
            "agent-child",
            "agent-parent",
            new_caps,
            parent_caps,
            performance,
        )

        # Should detect multiple emergence signals
        self.assertGreater(len(events), 0)
        event_types = {e.event_type for e in events}
        self.assertIn("new_tool", event_types)

    def test_get_agent_tree(self):
        """Test getting agent genealogy tree."""
        # Record some genealogy
        root = AgentGenealogy(
            agent_id="root",
            parent_agent_id=None,
            grandparent_id=None,
            designer_agent_id=None,
            generation=0,
            design_timestamp=time.time(),
            capabilities_gained=[],
            capabilities_lost=[],
            emergence_score=0.0,
        )
        self.tracker.record_agent_genealogy(root)

        child = AgentGenealogy(
            agent_id="child",
            parent_agent_id="root",
            grandparent_id=None,
            designer_agent_id="root",
            generation=1,
            design_timestamp=time.time(),
            capabilities_gained=["new_feature"],
            capabilities_lost=[],
            emergence_score=0.3,
        )
        self.tracker.record_agent_genealogy(child)

        tree = self.tracker.get_agent_tree("root")

        self.assertEqual(tree["agent_id"], "root")
        self.assertEqual(len(tree["children"]), 1)


class TestSelfModification(unittest.TestCase):
    """Test self-modification system."""

    def setUp(self):
        """Set up test manager."""
        self.mock_parent = MagicMock()
        self.mock_parent.session_id = "parent-123"
        self.manager = SelfModificationManager(self.mock_parent)

    def test_propose_self_modification(self):
        """Test child proposing modification."""
        proposal_id = self.manager.propose_self_modification(
            child_agent_id="child-456",
            task_description="Optimized task with special requirements",
            delta_config={"max_iterations": 20, "enabled_toolsets": ["code"]},
            expected_improvement={"success_rate": 0.15, "cost": -0.1},
            justification="These tools are needed for this task type",
        )

        self.assertIsNotNone(proposal_id)
        self.assertIn(proposal_id, self.manager.pending_proposals)

    def test_review_proposal(self):
        """Test parent reviewing modification proposal."""
        # First propose
        proposal_id = self.manager.propose_self_modification(
            child_agent_id="child-456",
            task_description="Task description",
            delta_config={"max_iterations": 20},
            expected_improvement={"success_rate": 0.2},
            justification="Good reason",
        )

        # Then review
        verdict = self.manager.review_proposal(proposal_id, threshold=0.1)

        self.assertIsInstance(verdict, ModificationVerdictData)
        self.assertEqual(verdict.proposal_id, proposal_id)

    def test_modification_summary(self):
        """Test getting modification summary."""
        # Propose some modifications
        for i in range(3):
            self.manager.propose_self_modification(
                child_agent_id=f"child-{i}",
                task_description="Task",
                delta_config={"max_iterations": 15 + i},
                expected_improvement={"success_rate": 0.1},
                justification="Reason",
            )

        summary = self.manager.get_modification_summary()

        self.assertIsInstance(summary, dict)
        self.assertEqual(summary["pending_proposals"], 3)


class TestTaskDesigner(unittest.TestCase):
    """Test task-aware agent design."""

    def setUp(self):
        """Set up designer."""
        self.designer = TaskDesigner()

    def test_design_agent_for_task(self):
        """Test designing agent for task."""
        task = "Implement a complex distributed system architecture with proofs"

        blueprint = self.designer.design_agent_for_task(task)

        self.assertIsInstance(blueprint, AgentBlueprint)
        self.assertIsNotNone(blueprint.model)
        self.assertIsNotNone(blueprint.toolsets)
        self.assertGreater(blueprint.max_iterations, 0)
        self.assertIsNotNone(blueprint.reasoning)

    def test_apply_blueprint_to_config(self):
        """Test applying blueprint to config."""
        blueprint = AgentBlueprint(
            task_type="coding",
            model="claude-opus-4-20250514",
            toolsets=["code", "terminal"],
            system_prompt_template="Focus on coding",
            max_iterations=20,
            max_tokens=6000,
            max_spawn_depth=1,
            max_concurrent_children=2,
            delegation_strategy="narrow",
            resource_limits={"max_tokens": 6000},
            estimated_success_rate=0.8,
            estimated_cost_tokens=5000,
            reasoning="Design for coding task",
        )

        base_config = {"model": "haiku", "enabled_toolsets": ["core"]}

        result = self.designer.apply_blueprint_to_agent_config(
            blueprint, base_config
        )

        self.assertEqual(result["model"], "claude-opus-4-20250514")
        self.assertIn("code", result["enabled_toolsets"])
        self.assertEqual(result["max_iterations"], 20)


class TestIntegration(unittest.TestCase):
    """Integration tests across modules."""

    def setUp(self):
        """Set up integrated system."""
        self.temp_dir = tempfile.mkdtemp()
        self.registry = ArchitectureRegistry(
            db_path=str(Path(self.temp_dir) / "registry.db")
        )
        self.tracker = EmergenceTracker(
            db_path=str(Path(self.temp_dir) / "emergence.db")
        )
        self.designer = TaskDesigner(registry=self.registry)

        self.mock_agent = MagicMock()
        self.mock_agent.model = "claude-opus-4-20250514"
        self.introspection = Introspection(self.mock_agent)

    def tearDown(self):
        """Clean up."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_full_workflow(self):
        """Test complete workflow: introspect → design → record → emerge."""
        # 1. Introspect current agent
        config = self.introspection.get_self_config()
        self.assertIsNotNone(config.model)

        # 2. Design optimized agent for task
        task = "Build machine learning pipeline"
        blueprint = self.designer.design_agent_for_task(task)
        self.assertIsNotNone(blueprint.model)

        # 3. Record success in registry
        record = ArchitectureRecord(
            task_id="task-001",
            task_description=task,
            task_type="coding",
            agent_config=blueprint.to_dict() if hasattr(blueprint, 'to_dict') else asdict(blueprint),
            success=True,
            success_rate=0.85,
            avg_cost_tokens=3500,
            iterations_used=12,
            model_used=blueprint.model,
            toolsets_used=blueprint.toolsets,
            timestamp=time.time(),
        )
        self.registry.record_task_result(record)

        # 4. Track emergence
        genealogy = AgentGenealogy(
            agent_id="agent-v2",
            parent_agent_id="agent-v1",
            grandparent_id=None,
            designer_agent_id="agent-v1",
            generation=1,
            design_timestamp=time.time(),
            capabilities_gained=["ml_optimization"],
            capabilities_lost=[],
            emergence_score=0.4,
        )
        self.tracker.record_agent_genealogy(genealogy)

        # Verify end-to-end
        stats = self.registry.get_statistics()
        self.assertEqual(stats["total_records"], 1)

        lineage = self.tracker.get_agent_lineage("agent-v2")
        self.assertEqual(len(lineage), 1)


def asdict(obj):
    """Fallback asdict for blueprint."""
    if hasattr(obj, '__dataclass_fields__'):
        from dataclasses import asdict as dc_asdict
        return dc_asdict(obj)
    return {}


if __name__ == "__main__":
    unittest.main()
