# Agentic Harness Implementation Guide

## Overview

This guide covers the production deployment of Hercules' **Agentic Harness** — a formal system for creating agents with proven correctness, deterministic execution, and audit trails.

**What is a harness?**
- Traditional agents: LLM loop with ad-hoc error handling
- **Harness-based agents**: FSM with formal guarantees, proof generation, and state management

## Five Core Components

### 1. Agent Interface (Foundation)

```python
from agent.harness import Agent, AgentState, ExecutionEngine, ResourceLimits

class MyAgent(Agent):
    def __init__(self):
        super().__init__("my_agent_id", "My Agent")
    
    def plan(self, task):
        # Return Plan object specifying execution steps
        pass
    
    def execute_step(self, step, context):
        # Execute one step, return result
        pass
```

**States:** IDLE → PLANNING → EXECUTING → (COMPLETE | FAILED | RECOVERING)

### 2. Execution Engine (Orchestration)

```python
engine = ExecutionEngine(
    agent=my_agent,
    limits=ResourceLimits(
        max_api_calls=50,
        max_tokens=4000,
        max_cost_usd=10.0,
    )
)

result = engine.execute(plan)
# Returns: ExecutionResult with trace, proof, resource usage
```

**Guarantees:**
- Resource limits enforced
- Steps executed in dependency order
- Full audit trail recorded
- Proof of correctness generated

### 3. State Management (Persistence)

```python
from agent.harness.state_manager import StateManager

state_mgr = StateManager("agent.db")

# Save checkpoint
checkpoint_id = state_mgr.save_checkpoint(
    step=42,
    state_data={"context": {...}},
    metadata={"approvals_pending": True}
)

# Recover from checkpoint
checkpoint = state_mgr.load_checkpoint(checkpoint_id)
# Automatically verifies SHA-256 integrity

# Immutable audit log
events = state_mgr.get_audit_log("error_detected")
```

**Features:**
- SQLite persistence
- SHA-256 integrity verification
- Immutable audit trail
- Instant recovery from checkpoint

### 4. Proof-Based Verification (Correctness)

```python
from agent.harness.proof_builder import ProofBuilder, ProofVerifier, VerificationLevel

# Build proof during execution
proof = ProofBuilder("proof_123", "refactor_code")
proof.add_precondition("Code is syntactically valid")
proof.add_step(
    step_num=1,
    description="Parse AST",
    precondition="File readable",
    action="ast.parse()",
    postcondition="AST generated"
)
proof.add_step_evidence(
    step_num=1,
    claim="AST parsing succeeded",
    evidence_type="code_analysis",
    data={"ast_nodes": 42},
    confidence=0.99
)

# Verify at different levels
verifier = ProofVerifier()
assert verifier.verify(proof, VerificationLevel.ASSERTION)  # Quick check
assert verifier.verify(proof, VerificationLevel.TRACE_VALIDATION)  # Replay
assert verifier.verify(proof, VerificationLevel.PROOF_VERIFICATION)  # Deep
```

**Verification Levels:**
1. **Assertion** — Runtime checks (O(1), 70% confidence threshold)
2. **Trace Validation** — Replay execution, verify step transitions (O(n))
3. **Proof Verification** — Check all evidence, high confidence (O(n×m))
4. **Model Checking** — Exhaustive state space (exponential, for small systems)

### 5. Agent Composition (Orchestration)

```python
from agent.harness.agent_algebra import Sequential, Parallel, Choice

# Define steps
steps = {
    "analyze": Step(...),
    "generate1": Step(...),
    "generate2": Step(...),
    "evaluate": Step(...),
}

# Create plan with dependencies
plan = Plan(
    steps=steps,
    dependencies={
        "analyze": [],
        "generate1": ["analyze"],
        "generate2": ["analyze"],
        "evaluate": ["generate1", "generate2"],
    }
)

# Execution order respects dependencies (topological sort)
execution_order = plan.topological_sort()
# → ["analyze", "generate1", "generate2", "evaluate"]
```

## Integration with Hercules

### Step 1: Update run_agent.py

```python
from agent.harness import ExecutionEngine, ResourceLimits
from agent.harness.state_manager import StateManager

# In AIAgent.__init__
self.harness_engine = ExecutionEngine(
    agent=self,
    limits=ResourceLimits(
        max_api_calls=config.max_api_calls,
        max_tokens=config.context_window,
        max_cost_usd=config.max_cost,
    )
)
self.state_manager = StateManager(f"~/.hercules/state/{session_key}.db")
```

### Step 2: Implement Agent Interface

```python
class AIAgent(Agent):
    def plan(self, task):
        """Generate execution plan from task."""
        steps = []
        # 1. Planning step
        steps.append(Step("plan", "Generate plan", ...))
        # 2. Tool gathering step
        steps.append(Step("gather", "Gather tools", ...))
        # 3. Execution steps
        for i, subtask in enumerate(task.subtasks):
            steps.append(Step(f"exec_{i}", f"Execute {subtask}", ...))
        # 4. Verification step
        steps.append(Step("verify", "Verify output", ...))
        
        return Plan(steps=steps, dependencies=deps)
    
    def execute_step(self, step, context):
        """Execute one step with proof generation."""
        # Generate proof
        proof = ProofBuilder(f"proof_{step.id}", step.name)
        proof.add_precondition("Step preconditions met")
        
        # Execute
        result = self._run_step(step, context)
        
        # Add evidence
        proof.add_evidence(
            claim=f"Step {step.id} succeeded",
            evidence_type="execution",
            data={"result": result},
        )
        
        return result
```

### Step 3: Run with Harness

```python
# In run_agent.py main loop
task = parse_user_input(messages)
plan = agent.plan(task)

result = agent.harness_engine.execute(plan)

if result.success:
    output = result.output
    audit_trail = result.trace
    proof = result.proof
else:
    error_msg = result.error
    # Recover from checkpoint if available
    checkpoint = agent.state_manager.load_checkpoint(...)
```

## Performance Profile

### Overhead Analysis

| Operation | Cost | Notes |
|-----------|------|-------|
| State checkpoint save | 2-5ms | SQLite write + SHA-256 |
| Checkpoint load + verify | 1-3ms | SQLite read + hash verify |
| Proof generation | 0.5-2ms | Per step, lightweight |
| Proof verification (L1) | <1ms | Assertion level |
| Proof verification (L3) | 1-10ms | Full verification |
| Message bus send | <1ms | In-memory queue |

**Total overhead per turn:** ~10-20ms (negligible vs. LLM latency)

## Real-World Example: Refactor Code

```python
class CodeRefactoringAgent(Agent):
    def plan(self, task: CodeRefactorTask):
        return Plan(
            steps={
                "analyze": Step("Analyze code structure", ...),
                "design1": Step("Design solution 1", ..., deps=["analyze"]),
                "design2": Step("Design solution 2", ..., deps=["analyze"]),
                "design3": Step("Design solution 3", ..., deps=["analyze"]),
                "evaluate": Step("Evaluate solutions", ..., deps=["design1", "design2", "design3"]),
                "implement": Step("Implement best", ..., deps=["evaluate"]),
                "test": Step("Run tests", ..., deps=["implement"]),
                "verify": Step("Verify refactoring", ..., deps=["test"]),
            },
            dependencies={...}
        )

# Parallel design generation: design1 || design2 || design3
# Then sequential verification: test → verify
# Full execution with proofs:
#   - Parallel phase: 3 design steps run concurrently
#   - Sequential phase: evaluate → implement → test → verify
#   - Each step generates proof with evidence
#   - Audit trail tracks every decision
```

**Result:**
```
ExecutionResult:
  success: true
  output: <refactored code>
  final_state: AgentState.COMPLETE
  trace: [45 entries]  # Every decision logged
  proof: {
    "proof_method": "trace_validation",
    "steps_executed": 8,
    "resources_within_limits": true,
  }
  resource_usage: {
    "api_calls": 12,
    "tokens_used": 2847,
    "cost_usd": 0.042,
  }
```

## Testing Harness Components

```python
# tests/harness/test_agent_lifecycle.py
def test_agent_execution_lifecycle():
    agent = TestAgent()
    plan = agent.plan(test_task)
    
    assert plan.validate()
    assert plan.topological_sort() == expected_order
    
    engine = ExecutionEngine(agent, ResourceLimits())
    result = engine.execute(plan)
    
    assert result.success
    assert result.final_state == AgentState.COMPLETE
    assert len(result.trace) == len(plan.steps)
    assert result.proof["resources_within_limits"]

# tests/harness/test_proof_verification.py
def test_proof_levels():
    proof = generate_test_proof()
    
    assert ProofVerifier.verify(proof, VerificationLevel.ASSERTION)
    assert ProofVerifier.verify(proof, VerificationLevel.TRACE_VALIDATION)
    assert ProofVerifier.verify(proof, VerificationLevel.PROOF_VERIFICATION)

# tests/harness/test_state_recovery.py
def test_checkpoint_recovery():
    mgr = StateManager(":memory:")
    
    ckpt_id = mgr.save_checkpoint(10, {"data": "test"})
    ckpt = mgr.load_checkpoint(ckpt_id)
    
    assert ckpt.step == 10
    assert ckpt.verify_integrity()
```

## Migration Path

### Phase 1: Foundation (Week 1)
- ✓ Agent interface created
- ✓ Execution engine created
- ✓ State manager created
- [ ] Add to run_agent.py imports
- [ ] Create wrapper for existing agent

### Phase 2: Integration (Week 2)
- [ ] Update conversation_loop to use harness
- [ ] Migrate execution to harness engine
- [ ] Add proof generation to existing tools
- [ ] Create checkpoints on every turn

### Phase 3: Verification (Week 3)
- [ ] Add proof verification level selection
- [ ] Create proof dashboard
- [ ] Export audit trails for audit
- [ ] Integrate with approval system

### Phase 4: Scale (Week 4)
- [ ] Multi-agent coordination via message bus
- [ ] Distributed agent mesh
- [ ] Real-time observability
- [ ] Machine learning on execution patterns

## Advantages Over Current Approach

**Transparency**
- Every decision logged and auditable
- Proof of why decision made
- Impossible to have "black box" failures

**Correctness**
- Formal guarantees (safety, liveness)
- Deterministic replay
- Proof-based verification

**Composability**
- Agents can be composed algebraically
- Dependencies automatically managed
- Parallel execution where possible

**Reliability**
- Atomic checkpoints at every step
- Instant recovery from failure
- Resource limits enforced

## Troubleshooting

**Agent stuck in EXECUTING state**
- Check for deadlock: circular dependencies in plan
- Check for livelock: infinite loops in step execution
- Verify all steps have timeouts configured

**Proof verification fails**
- Check preconditions of first step match spec
- Verify step postconditions link to next preconditions
- Increase verification level for detailed diagnostics

**Checkpoint recovery fails**
- Verify checkpoint integrity (SHA-256 hash)
- Check state format is compatible
- Ensure step IDs haven't changed

## Performance Tuning

### Checkpoint Frequency
- **Every step**: Maximum safety, ~2-5ms overhead
- **Every N steps**: Balance safety/performance (recommended N=5)
- **On error**: Minimal overhead, only for recovery

### Proof Generation Level
- **Fast path**: Assertion level (0.5ms), for production
- **Detailed**: Trace validation (2ms), for debugging
- **Exhaustive**: Proof verification (5-10ms), for critical code

### Resource Limits
```python
# Conservative (safe, slower)
limits = ResourceLimits(
    max_api_calls=30,
    max_tokens=2000,
    max_cost_usd=5.0,
)

# Aggressive (faster, riskier)
limits = ResourceLimits(
    max_api_calls=100,
    max_tokens=8000,
    max_cost_usd=20.0,
)
```

## Next Steps

1. **Read** AGENTIC_HARNESS_ARCHITECTURE.md for theory
2. **Study** agent/harness/__init__.py for API
3. **Run** python agent/harness/example_integrated_harness.py
4. **Integrate** into run_agent.py following migration path
5. **Test** with existing agent workflows
6. **Deploy** with Phase 1 foundation

---

**Key Insight:** The best agent is not the one with the smartest LLM, but the one with the strongest guarantees.

Hercules' agentic harness provides those guarantees.
