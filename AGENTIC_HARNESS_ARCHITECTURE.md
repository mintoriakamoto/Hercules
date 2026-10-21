# Agentic Harness Architecture: Deep Framework Design

## Core Thesis

Current agents (Copilot, Cursor, Replit) treat agents as **monolithic LLM loops**.
Hercules should treat agents as **formal systems with provable properties**.

This document defines the foundational architecture for:
1. **Agent Interface Protocol** (how agents communicate)
2. **Execution Engine** (how agents run)
3. **State Machine** (how agents maintain consistency)
4. **Verification Framework** (how we prove correctness)
5. **Composition System** (how agents coordinate)

---

## SECTION 1: FORMAL AGENT MODEL

### 1.1 Agent as a Finite State Machine

```
Agent ::= (States, Events, Transitions, Init, Final)

Where:
  States     = {IDLE, PLANNING, EXECUTING, RECOVERING, COMPLETE, FAILED}
  Events     = {task_start, subtask_created, error_detected, recovery_success, task_complete}
  Transitions = {(from_state, event) → (to_state, actions)}
  Init       = IDLE
  Final      = {COMPLETE, FAILED}
```

### 1.2 Agent Execution Trace

Every agent execution produces an **audit trail**:

```
Trace = [
  {timestamp, state, event, input, output, resources_used, decision_made},
  ...
]
```

### 1.3 Agent Invariants

Properties that MUST hold true:

```
Invariant 1: Safety
  - No side effect without approval
  - No resource limit exceeded
  - No state mutation without checkpoint

Invariant 2: Determinism (in logs)
  - Same input + same state → same output
  - Enables replay, testing, verification

Invariant 3: Causality
  - Effects only from causes in scope
  - No time-travel or out-of-order execution

Invariant 4: Convergence
  - Agent must reach final state
  - No infinite loops (liveness)
  - No deadlock (no circular waits)
```

---

## SECTION 2: AGENT EXECUTION ENGINE

### 2.1 Multi-Layer Execution Stack

```
Layer 4: Orchestration (multi-agent coordination)
         [Agent Mesh, Federation, Delegation]
         
Layer 3: Execution (single agent lifecycle)
         [State Machine, Transition Engine, Recovery Loop]
         
Layer 2: Reasoning (LLM interaction)
         [Prompt Template, Context Management, Response Parsing]
         
Layer 1: Foundation (core services)
         [State Storage, Event Log, Resource Manager]
```

### 2.2 Agent Lifecycle

```
CREATE
  ↓
INIT (load state, verify invariants)
  ↓
PLAN (generate execution steps)
  ↓
EXECUTE (run each step with monitoring)
  ↓ [success path]
VERIFY (check output against spec)
  ↓
COMPLETE + CLEANUP
  
  ↓ [error path]
RECOVER (diagnose + attempt fix)
  ↓
RETRY or FAIL

Formal specification:
  step: (input: State, task: Task) → (output: State, trace: Trace, status: Status)
  execute: (agents: [Agent], plan: Plan) → (final_state: State, audit_log: Log)
```

### 2.3 Execution Guarantees

```
Type 1: At-Most-Once
  - Task executed 0 or 1 times, never duplicated
  - Uses: idempotency keys, atomic transactions

Type 2: At-Least-Once
  - Task executed 1+ times if needed
  - Uses: retries with exponential backoff

Type 3: Exactly-Once
  - Task executed exactly 1 time
  - Uses: distributed consensus (2-phase commit)

Hercules achieves: At-Most-Once by default, Exactly-Once with proof verification
```

---

## SECTION 3: STATE MANAGEMENT FRAMEWORK

### 3.1 Hierarchical State Model

```
GlobalState
├── SessionState
│   ├── TaskState
│   │   ├── ExecutionState
│   │   ├── ResourceState
│   │   └── ApprovalState
│   ├── ContextWindow
│   └── Checkpoints
└── PersistentState (SQLite)
    ├── Audit Log
    ├── Decision Log
    ├── Artifact Registry
    └── Capability Profile
```

### 3.2 State Transitions (Formal Grammar)

```
S₀ → S₁ := (preconditions met) ∧ (effect applied) ∧ (invariants preserved)

Valid transition requires:
  1. Preconditions: Required conditions before transition
  2. Guard: Check resource limits, approvals, safety
  3. Effect: Update state atomically
  4. Postconditions: Verify new state is valid
  5. Log: Record transition in audit trail
```

### 3.3 Checkpoint Protocol

```
Checkpoint := (version, timestamp, state_hash, metadata)

Save checkpoint:
  1. Serialize agent state
  2. Compute SHA-256 hash
  3. Store with metadata (which step, resources used, approvals)
  4. Return checkpoint_id

Resume from checkpoint:
  1. Verify checkpoint integrity (hash match)
  2. Load state atomically
  3. Continue from step N+1
  4. Log: "resumed from checkpoint_id"
```

---

## SECTION 4: VERIFICATION FRAMEWORK

### 4.1 Proof-Based Correctness

Instead of just testing output, **prove correctness**:

```
Correctness Proof := {
  precondition: "Task input valid",
  steps: [
    "Step 1: Analyzed code structure",
    "Step 2: Generated 3 solutions",
    "Step 3: Picked best via evaluator",
  ],
  postcondition: "Output satisfies requirements",
  evidence: {
    code_analysis: <AST dump>,
    evaluations: [score1, score2, score3],
    selection: "solution_2 (score=0.92)",
  }
}
```

### 4.2 Verification Levels

```
Level 1: Assertion (quick, local)
  - Runtime checks during execution
  - Cost: O(1) per check
  - Example: "file exists before modification"

Level 2: Trace Validation (audit)
  - Replay execution, verify each step
  - Cost: O(n) where n = steps
  - Example: "each function call had valid args"

Level 3: Proof Verification (thorough)
  - Re-execute proof steps independently
  - Cost: O(n×m) where m = proof depth
  - Example: "solution actually compiles and tests pass"

Level 4: Model Checking (exhaustive)
  - Formal state-space exploration
  - Cost: Exponential (for small systems)
  - Example: "no reachable state violates safety"
```

### 4.3 Specification Language

```
spec Task {
  input: CodeFile
  preconditions: {
    file_exists(input),
    file_readable(input),
    valid_python(input),
  }
  
  steps: [
    analyze_ast → AST,
    generate_solutions(AST) → [Solution],
    evaluate_solutions([Solution]) → (best: Solution, scores: Scores),
    implement(best) → Output,
  ]
  
  postconditions: {
    output_valid_python(Output),
    output_compiles(Output),
    tests_pass(Output),
  }
  
  invariants: {
    resources_within_limits(),
    no_unapproved_side_effects(),
  }
}
```

---

## SECTION 5: COMPOSITION & ORCHESTRATION

### 5.1 Agent Algebra (Formal Operators)

```
Operator 1: Sequential Composition (→)
  A → B := Execute A, then B with A's output
  Associative: (A → B) → C = A → (B → C)
  
Operator 2: Parallel Composition (||)
  A || B := Execute A and B concurrently
  Commutative: A || B = B || A
  
Operator 3: Choice (⊕)
  A ⊕ B := Execute A; if fails, execute B
  
Operator 4: Iteration (*)
  A* := Execute A repeatedly until convergence or limit
  
Operator 5: Conditional (?)
  A ? B : C := If A succeeds, execute B, else C
```

### 5.2 Plan as Executable Expression

```
Example plan (English):
"Analyze code, generate 3 approaches, pick best, implement, verify"

Formal expression:
  Analyzer → (GenerateSolutions || GenerateSolutions || GenerateSolutions) 
    → Evaluator 
    → Implementer 
    → Verifier

Execution semantics:
  - Analyzer runs first (sequential)
  - 3 GenerateSolutions run in parallel
  - Evaluator runs after all generators finish (barrier)
  - Implementer runs next
  - Verifier runs last
  
Formal guarantees:
  - No race conditions (dependencies enforced)
  - Deterministic execution order
  - Provably correct (if each step correct, composition correct)
```

### 5.3 Agent Communication Protocol

```
Message := {
  from: AgentID,
  to: AgentID,
  type: ("REQUEST" | "RESPONSE" | "EVENT"),
  payload: {
    task: Task,
    state: State,
    resources: ResourceAllocation,
  },
  timestamp: Epoch,
  correlation_id: UUID,  # for tracing across agents
}

Guarantees:
  - Messages delivered at-most-once (idempotency key)
  - Delivery order preserved per sender-receiver pair
  - Timeout if no response within deadline
  - Async + await pattern for coordination
```

---

## SECTION 6: RESOURCE MANAGEMENT

### 6.1 Resource Model

```
Resources := {
  compute: {
    api_calls: Counter,
    tokens: Counter,
    latency_budget_ms: Gauge,
  },
  memory: {
    context_tokens: Gauge,
    checkpoint_size_mb: Gauge,
  },
  cost: {
    usd_spent: Counter,
    usd_budget: Gauge,
  },
  approvals: {
    pending_count: Gauge,
    response_timeout_s: Duration,
  },
}
```

### 6.2 Resource Allocation Strategy

```
Allocation := (agent_id, resource_type, amount, duration)

Strategy 1: Static (fixed amounts per agent)
  - Simple, predictable
  - Inflexible for variable workloads
  
Strategy 2: Dynamic (proportional to complexity)
  - More efficient
  - Requires estimation phase
  
Strategy 3: Adaptive (learn from history)
  - Best for repeated tasks
  - Requires learning capability

Hercules uses: Strategy 2 (dynamic) + Strategy 3 (adaptive)
```

### 6.3 Resource Enforcement

```
Layer 1: Budgeting (before execution)
  - Estimate resource needs
  - Check available budget
  - Reject if insufficient

Layer 2: Monitoring (during execution)
  - Track actual usage
  - Alert if approaching limit (80%)
  - Force graceful shutdown if exceeded

Layer 3: Metering (after execution)
  - Final accounting
  - Update remaining budget
  - Log for analytics
```

---

## SECTION 7: ERROR RECOVERY FRAMEWORK

### 7.1 Error Taxonomy

```
ErrorClass 1: User Error (precondition not met)
  - Malformed input
  - Invalid task specification
  - Missing required approvals
  Recovery: Reject, ask user to fix

ErrorClass 2: System Error (transient failure)
  - Network timeout
  - Temporary API overload
  - Rate limit exceeded
  Recovery: Retry with backoff

ErrorClass 3: Safety Error (invariant violation)
  - Attempting unapproved side effect
  - Resource limit exceeded
  - State corruption detected
  Recovery: Halt immediately, manual intervention

ErrorClass 4: Semantic Error (task logic failure)
  - Solution doesn't compile
  - Tests fail
  - Output doesn't match spec
  Recovery: Replan or delegate to human
```

### 7.2 Recovery State Machine

```
ErrorDetected
  ↓
Classify (which error type?)
  ├─→ User Error: Reject + return message
  ├─→ System Error: Backoff + retry (up to N times)
  ├─→ Safety Error: Halt + alert
  └─→ Semantic Error: Replan or escalate

Tracking:
  - error_count: how many errors so far?
  - error_history: what kind of errors?
  - recovery_success_rate: what percentage of errors recovered?
```

### 7.3 Formal Recovery Invariants

```
Invariant 1: Progress
  - Every error recovery attempt must make progress toward goal
  - Or prove it's unrecoverable and halt

Invariant 2: Termination
  - Maximum N recovery attempts
  - After N attempts, escalate to human
  - No infinite retry loops

Invariant 3: Safety
  - Recovery never violates core safety constraints
  - Better to fail than to succeed unsafely
```

---

## SECTION 8: REFERENCE IMPLEMENTATION

### 8.1 Minimal Viable Harness (MVH)

Core components (order of implementation):

```
Phase 1: Foundation (Week 1)
├─ agent_interface.py
│  └─ Abstract Agent class with lifecycle methods
├─ execution_engine.py
│  └─ State machine + transition logic
├─ state_manager.py
│  └─ Checkpoint save/load + SQLite storage
└─ event_log.py
   └─ Immutable audit trail

Phase 2: Verification (Week 2)
├─ proof_builder.py
│  └─ Specification + evidence collection
├─ verifier.py
│  └─ Multiple verification levels
└─ trace_validator.py
   └─ Replay and validate execution traces

Phase 3: Composition (Week 3)
├─ agent_algebra.py
│  └─ Sequential, parallel, choice operators
├─ plan_executor.py
│  └─ Execute composition expressions
└─ message_bus.py
   └─ Agent-to-agent communication

Phase 4: Resources (Week 4)
├─ resource_manager.py
│  └─ Budget tracking + enforcement
├─ recovery_framework.py
│  └─ Error classification + recovery strategies
└─ observability.py
   └─ Real-time metrics + dashboard
```

### 8.2 Example: Harness-Based Agent

```python
# Define agent interface
class CodeRefactorAgent(Agent):
    def plan(self, task: Task) -> Plan:
        # Generate execution plan
        return Plan([
            Analyzer(task.file),
            GenerateSolutions(3),  # parallel
            Evaluator(),
            Implementer(),
            Verifier(),
        ])
    
    def execute(self, plan: Plan) -> Result:
        # Run through execution engine
        # Automatically handles:
        # - State management
        # - Checkpointing
        # - Resource limits
        # - Error recovery
        # - Proof generation
        return self.engine.execute(plan)

# Run agent
agent = CodeRefactorAgent()
result = agent.run(
    task=RefactorTask(...),
    resources=ResourceLimits(tokens=4000, cost=5.0),
    approval_required=True,
)

# Result includes:
# - final_output
# - execution_trace
# - proof_of_correctness
# - audit_log
# - resource_usage
```

---

## SECTION 9: ADVANTAGES OVER CURRENT ARCHITECTURE

### Current Approach (Copilot, Cursor)
```
LLM loop:
  while not done:
    context = get_context()
    response = llm(context)
    action = parse(response)
    execute(action)

Problems:
- No formal guarantees
- Opaque decision-making
- Ad-hoc error handling
- Difficult to verify correctness
- Impossible to resume from failure
- No resource accounting
```

### Hercules Agentic Harness
```
Formal execution:
  agent.run(task, resources, approvals)
  → [state_machine]
  → [execute_with_guarantees]
  → [generate_proof]
  → [audit_trail]

Advantages:
✓ Formal guarantees (safety, liveness)
✓ Explicit state transitions
✓ Proof-based verification
✓ Deterministic replay
✓ Atomic checkpointing
✓ Full resource accounting
✓ Classified error recovery
✓ Composable agents
✓ Transparent audit trail
```

---

## SECTION 10: INTEGRATION WITH HERCULES

### 10.1 How It Fits

```
Current Hercules:
├─ Fast inference engine ✓
├─ Tool orchestration ✓
├─ Context optimization ✓
├─ Error recovery ✓
├─ Performance tracking ✓
└─ Autonomy control ✓

New Agentic Harness:
├─ Formal agent interface (NEW)
├─ State machine execution (NEW)
├─ Proof-based verification (ENHANCE)
├─ Agent composition algebra (NEW)
├─ Message bus protocol (NEW)
└─ Resource enforcement layer (ENHANCE)

Integration points:
- run_agent.py → Use harness execution engine
- conversation_loop.py → Implement state machine protocol
- tools/approval.py → Integrate with resource enforcement
- tools/proofs.py → Use proof builder
```

### 10.2 Deployment Timeline

```
Week 1: Agent Interface + Execution Engine
  - Define Agent base class
  - Implement state machine
  - Basic checkpoint save/load
  
Week 2: Verification Framework
  - Proof builder
  - Trace validator
  - Multiple verification levels
  
Week 3: Composition System
  - Agent algebra operators
  - Plan executor
  - Message bus
  
Week 4: Resource Management
  - Budget enforcement
  - Recovery framework
  - Observability
  
Result: Hercules becomes the only agent system with formal guarantees
```

---

## CONCLUSION

This architecture transforms Hercules from a **monolithic LLM loop** into a **formal agent system**.

Key insight: **The best agent is not the one with the smartest LLM, but the one with the strongest guarantees.**

- Correctness: Proof-based verification
- Safety: Resource limits + approval gates
- Transparency: Immutable audit trail
- Composability: Agent algebra
- Reliability: Formal state machine
- Reproducibility: Deterministic execution

Hercules becomes **the enterprise-grade agent platform** for mission-critical coding tasks.

---

## Next: Implementation

Begin Phase 1:
- [ ] agent_interface.py (abstract Agent base class)
- [ ] execution_engine.py (state machine)
- [ ] state_manager.py (checkpoint protocol)
- [ ] event_log.py (audit trail)

Expected: Full harness operational in 4 weeks
Impact: 10x improvement in reliability, 5x improvement in transparency
