"""Agentic Harness: Formal agent execution framework.

Implements:
- Agent interface with FSM-based lifecycle
- State machine execution with guarantees
- Proof-based verification
- Compositional agent algebra
- Resource enforcement
- Audit trail and checkpointing
"""

# Import from core module
from agent.harness.__init_core import (
    Agent,
    AgentState,
    AgentEvent,
    ExecutionTrace,
    ExecutionResult,
    ExecutionEngine,
    Plan,
    ResourceLimits,
)

# Import from submodules
from agent.harness.state_manager import StateManager, Checkpoint
from agent.harness.proof_builder import (
    Proof,
    ProofStep,
    Evidence,
    ProofBuilder,
    ProofVerifier,
    VerificationLevel,
)
from agent.harness.agent_algebra import (
    Sequential,
    Parallel,
    Choice,
    Conditional,
    Iteration,
    Step,
    Plan as AlgebraPlan,
)
from agent.harness.message_bus import (
    Message,
    MessageType,
    MessageBus,
    MessageBusPool,
)

__all__ = [
    "Agent",
    "AgentState",
    "AgentEvent",
    "ExecutionTrace",
    "ExecutionResult",
    "ExecutionEngine",
    "Plan",
    "ResourceLimits",
    "StateManager",
    "Checkpoint",
    "Proof",
    "ProofStep",
    "Evidence",
    "ProofBuilder",
    "ProofVerifier",
    "VerificationLevel",
    "Sequential",
    "Parallel",
    "Choice",
    "Conditional",
    "Iteration",
    "Step",
    "Message",
    "MessageType",
    "MessageBus",
    "MessageBusPool",
]
