"""Tests for agentic harness core functionality."""

import json
import tempfile
from pathlib import Path
from agent.harness import (
    Agent, AgentState, AgentEvent, ExecutionEngine,
    ResourceLimits, Plan, Step, ExecutionResult
)
from agent.harness.state_manager import StateManager
from agent.harness.proof_builder import ProofBuilder, ProofVerifier, VerificationLevel
from agent.harness.agent_algebra import Sequential, Parallel, Choice


class TestAgent(Agent):
    """Test agent implementation."""

    def __init__(self):
        super().__init__("test_agent", "Test Agent")

    def plan(self, task):
        steps = {
            "step1": Step("step1", "First step", lambda x: {"output": "step1"}, []),
            "step2": Step("step2", "Second step", lambda x: {"output": "step2", "depends_on": x}, ["step1"]),
        }
        return Plan(
            steps=steps,
            dependencies={"step1": [], "step2": ["step1"]}
        )

    def execute_step(self, step, context):
        return step.execute(context)


def test_agent_lifecycle():
    """Test agent state transitions."""
    agent = TestAgent()
    
    assert agent.state == AgentState.IDLE
    assert len(agent.trace) == 0
    
    # Simulate execution
    agent.state = AgentState.PLANNING
    assert agent.state == AgentState.PLANNING
    
    agent.state = AgentState.EXECUTING
    agent.record_trace(
        AgentEvent.EXECUTION_START,
        {"steps": 2},
        {},
        {},
    )
    
    assert len(agent.trace) == 1
    assert agent.trace[0].event == AgentEvent.EXECUTION_START


def test_execution_engine_basic():
    """Test basic execution engine functionality."""
    agent = TestAgent()
    engine = ExecutionEngine(agent, ResourceLimits(max_api_calls=10))
    
    plan = agent.plan(None)
    assert plan.validate()
    
    result = engine.execute(plan)
    
    assert isinstance(result, ExecutionResult)
    assert result.final_state in [AgentState.COMPLETE, AgentState.FAILED]
    assert len(result.trace) > 0


def test_plan_validation():
    """Test plan validation."""
    steps = {
        "a": Step("a", "A", lambda x: x, []),
        "b": Step("b", "B", lambda x: x, ["a"]),
    }
    
    plan = Plan(steps=steps, dependencies={"a": [], "b": ["a"]})
    assert plan.validate()
    
    # Circular dependency should fail
    plan_circular = Plan(
        steps=steps,
        dependencies={"a": ["b"], "b": ["a"]}
    )
    assert not plan_circular.validate()


def test_plan_topological_sort():
    """Test topological sorting of plan."""
    steps = {
        "a": Step("a", "A", lambda x: x, []),
        "b": Step("b", "B", lambda x: x, []),
        "c": Step("c", "C", lambda x: x, ["a", "b"]),
    }
    
    plan = Plan(
        steps=steps,
        dependencies={"a": [], "b": [], "c": ["a", "b"]}
    )
    
    order = plan.topological_sort()
    
    # c must come after both a and b
    assert order.index("c") > max(order.index("a"), order.index("b"))


def test_state_manager_checkpoint():
    """Test checkpoint save and load."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        mgr = StateManager(str(db_path))
        
        # Save checkpoint
        ckpt_id = mgr.save_checkpoint(
            step=42,
            state_data={"test": "data", "count": 100},
            metadata={"reason": "test"}
        )
        
        # Load checkpoint
        ckpt = mgr.load_checkpoint(ckpt_id)
        
        assert ckpt is not None
        assert ckpt.step == 42
        assert ckpt.state_data["test"] == "data"
        assert ckpt.verify_integrity()


def test_state_manager_audit_log():
    """Test audit log functionality."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        mgr = StateManager(str(db_path))
        
        # Log events
        mgr.log_event("task_started", {"task": "test"})
        mgr.log_event("step_completed", {"step": 1})
        mgr.log_event("error_detected", {"error": "test error"})
        
        # Get all events
        all_events = mgr.get_audit_log()
        assert len(all_events) == 3
        
        # Get specific event type
        errors = mgr.get_audit_log("error_detected")
        assert len(errors) == 1
        assert "test error" in errors[0]["data"]["error"]


def test_proof_builder():
    """Test proof building."""
    proof_builder = ProofBuilder("proof_1", "test_task")
    
    proof_builder.add_precondition("Task input valid")
    proof_builder.add_postcondition("Task completed successfully")
    
    step = proof_builder.add_step(
        step_num=1,
        description="Analyze input",
        precondition="Input available",
        action="parse(input)",
        postcondition="Parsed successfully"
    )
    
    proof_builder.add_step_evidence(
        step_num=1,
        claim="Input was valid",
        evidence_type="assertion",
        data={"lines": 100},
        confidence=0.95
    )
    
    proof = proof_builder.build()
    
    assert proof.task == "test_task"
    assert len(proof.steps) == 1
    assert proof.steps[0].step_num == 1
    assert len(proof.steps[0].evidence) == 1


def test_proof_verification_levels():
    """Test proof verification at different levels."""
    proof_builder = ProofBuilder("proof_1", "test")
    proof_builder.add_precondition("Start")
    proof_builder.add_postcondition("End")
    
    step = proof_builder.add_step(
        step_num=1,
        description="Test",
        precondition="Start",
        action="Execute",
        postcondition="End"
    )
    
    proof_builder.add_step_evidence(
        step_num=1,
        claim="Execution succeeded",
        evidence_type="test",
        data={"result": True},
        confidence=0.99
    )
    
    proof = proof_builder.build()
    
    # Verify at different levels
    assert ProofVerifier.verify(proof, VerificationLevel.ASSERTION)
    assert ProofVerifier.verify(proof, VerificationLevel.TRACE_VALIDATION)
    assert ProofVerifier.verify(proof, VerificationLevel.PROOF_VERIFICATION)


def test_resource_limits():
    """Test resource limit enforcement."""
    limits = ResourceLimits(
        max_api_calls=5,
        max_tokens=1000,
        max_cost_usd=1.0,
    )
    
    assert limits.max_api_calls == 5
    assert limits.max_tokens == 1000
    assert limits.max_cost_usd == 1.0


if __name__ == "__main__":
    test_agent_lifecycle()
    test_execution_engine_basic()
    test_plan_validation()
    test_plan_topological_sort()
    test_state_manager_checkpoint()
    test_state_manager_audit_log()
    test_proof_builder()
    test_proof_verification_levels()
    test_resource_limits()
    print("✓ All harness tests passed")
