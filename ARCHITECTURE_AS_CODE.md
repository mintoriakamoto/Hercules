# Architecture as Code: Self-Designing Agents in Hercules

## Overview

The Architecture as Code system enables exponential capability growth through agents that design better agents recursively. This document describes the system architecture, components, and integration points.

## Vision

Instead of humans manually tuning agent configurations, agents learn from their execution history and:
1. **Introspect** their own configuration and capabilities
2. **Design** optimized variants for specific tasks
3. **Learn** from successful architectures via a registry
4. **Modify** themselves by proposing improvements
5. **Emerge** with new capabilities through recursive design

## Core Components

### 1. Agent Introspection API (`agent/meta/introspection.py`)

**Purpose**: Self-awareness for agents.

Provides agents with mechanisms to understand:
- Their own configuration (model, toolsets, system prompt)
- Available capabilities (tools, models, success rates)
- Performance history (cost, iterations, success)
- Capability gaps (what they can't do yet)

**Key Classes**:
- `Introspection`: Main API
- `AgentConfig`: Complete configuration snapshot
- `CapabilityProfile`: Capabilities summary
- `TaskPerformance`: Single task execution record
- `CapabilityGap`: Identified limitation

**Example Usage**:
```python
from agent.meta.introspection import Introspection

introspect = Introspection(agent)
config = introspect.get_self_config()
capabilities = introspect.query_self_capabilities()
gaps = introspect.estimate_capability_gap("Design distributed system")
```

### 2. Agent Design API (`agent/meta/design.py`)

**Purpose**: Generate optimized agent configurations.

Enables agents to propose specialized configurations based on:
- Task requirements (tools, reasoning, context)
- Available resources (token budget, time)
- Performance history (past successes)

**Key Classes**:
- `Design`: Main API
- `AgentVariant`: Proposed configuration
- `ToolsetComposition`: Tool set assembly

**Example Usage**:
```python
from agent.meta.design import Design

design = Design(agent, registry=registry)
variant = design.propose_agent_variant(
    goal="Design ML pipeline",
    context={},
    budget={"max_tokens": 10000}
)
toolset = design.compose_toolset(
    task_requirements=["code", "file_ops"],
    cost_budget={"max_tokens": 8000}
)
```

### 3. Architecture Learning Registry (`agent/meta/registry.py`)

**Purpose**: Learn from successful task-agent pairings.

SQLite database that records:
- Task descriptions and types
- Agent configurations used
- Success rates and costs
- Task type classifications

Enables:
- Similarity-based lookup for similar tasks
- Statistics on which configurations work best
- Reuse of proven architectures

**Key Classes**:
- `ArchitectureRegistry`: Main API
- `ArchitectureRecord`: Single task-agent pairing

**Database Schema**:
```sql
CREATE TABLE architecture_records (
    task_id TEXT,
    task_description TEXT,
    task_type TEXT,
    agent_config TEXT (JSON),
    success BOOLEAN,
    success_rate REAL,
    avg_cost_tokens REAL,
    iterations_used INTEGER,
    model_used TEXT,
    toolsets_used TEXT (JSON),
    timestamp REAL,
    designer_agent_id TEXT,
    emergence_score REAL
)
```

**Example Usage**:
```python
from agent.meta.registry import ArchitectureRegistry, ArchitectureRecord

registry = ArchitectureRegistry()

# Record successful task
record = ArchitectureRecord(
    task_id="task-001",
    task_description="Implement sorting algorithm",
    task_type="coding",
    agent_config={"model": "claude-opus", ...},
    success=True,
    success_rate=0.95,
    ...
)
registry.record_task_result(record)

# Look up similar
config = registry.lookup_successful_architecture(
    "Create Python sorting code"
)
```

### 4. Capability Emergence Tracking (`agent/meta/emergence.py`)

**Purpose**: Detect when recursive design creates new capabilities.

Tracks agent genealogy and identifies emergence patterns:
- New tools discovered
- Success on previously-impossible tasks
- Cost improvements
- Novel problem-solving approaches

**Key Classes**:
- `EmergenceTracker`: Main API
- `AgentGenealogy`: Lineage information
- `EmergenceEvent`: Single emergence signal

**Example Usage**:
```python
from agent.meta.emergence import EmergenceTracker, EmergenceEvent

tracker = EmergenceTracker()

# Record agent lineage
genealogy = AgentGenealogy(
    agent_id="agent-v2",
    parent_agent_id="agent-v1",
    generation=1,
    capabilities_gained=["new_tool"],
    emergence_score=0.4
)
tracker.record_agent_genealogy(genealogy)

# Detect emergence signals
events = tracker.detect_emergence(
    agent_id="agent-v2",
    parent_agent_id="agent-v1",
    new_capabilities=["tool_a", "tool_b"],
    parent_capabilities=["tool_a"],
    performance_vs_parent={
        "parent_cost": 2000,
        "child_cost": 1500,
        ...
    }
)
```

### 5. Self-Modifying Delegation (`agent/delegation/self_modify.py`)

**Purpose**: Enable child→parent configuration improvements.

Pattern:
1. Child agent completes task successfully
2. Child analyzes why it succeeded
3. Child proposes configuration delta to parent
4. Parent validates via consensus proof
5. Parent adopts if improvement is genuine
6. Modification propagates via registry

**Key Classes**:
- `SelfModificationManager`: Parent-side management
- `ConfigModificationProposal`: Child's proposal
- `ModificationVerdictData`: Parent's decision

**Example Usage**:
```python
from agent.delegation.self_modify import SelfModificationManager

manager = SelfModificationManager(parent_agent)

# Child proposes improvement
proposal_id = manager.propose_self_modification(
    child_agent_id="child-456",
    task_description="Complex task with special needs",
    delta_config={"max_iterations": 25, "enabled_toolsets": ["code"]},
    expected_improvement={"success_rate": 0.15},
    justification="Need extended iterations for this task"
)

# Parent reviews
verdict = manager.review_proposal(proposal_id, threshold=0.1)
if verdict.accepted:
    # Modification applied
    pass
```

### 6. Task-Aware Agent Design (`agent/planning/task_designer.py`)

**Purpose**: Customize agents for specific task classes.

Before delegating, analyzes task and:
- Infers task type (coding, analysis, planning, research, creative)
- Estimates complexity and resource needs
- Looks up similar successful tasks
- Designs optimized agent variant
- Provides complete blueprint for subagent spawn

**Key Classes**:
- `TaskDesigner`: Main API
- `TaskAnalysis`: Task requirements
- `AgentBlueprint`: Complete agent spec

**Example Usage**:
```python
from agent.planning.task_designer import TaskDesigner

designer = TaskDesigner(registry=registry, introspection=introspect)

# Design agent for task
blueprint = designer.design_agent_for_task(
    "Implement WebSocket server with tests"
)

# Apply to agent config
config = designer.apply_blueprint_to_agent_config(
    blueprint, 
    base_config={"model": "haiku", ...}
)

# Spawn subagent with optimized config
delegate_task(..., config=config)
```

### 7. Integration Layer (`agent/meta/integration.py`)

**Purpose**: Unified interface to the complete system.

Provides high-level API for incorporating metaprogramming into agent runtime.

**Key Classes**:
- `MetaprogrammingSystem`: Unified interface
- Helper functions: `setup_metaprogramming()`, `record_task_execution()`, `design_subagent()`

**Example Usage**:
```python
from agent.meta.integration import setup_metaprogramming, record_task_execution

# Initialize during agent startup
metaprog = setup_metaprogramming(agent)

# Record task execution
task_id = record_task_execution(
    metaprog,
    task_description="Build API server",
    success=True,
    cost_tokens=3500,
    iterations_used=12,
    tools_used=["bash", "code"],
    execution_time_seconds=45.2
)

# Design subagent
subagent_config = metaprog.design_subagent_config(
    "Optimize database queries"
)
```

## Integration Points

### In Delegation System (`tools/delegate_tool.py`)

Before spawning a child agent:
```python
# Design optimized child config
if metaprogramming:
    child_config = design_subagent(metaprogramming, task_description)
    # Apply to child agent initialization
```

After child completes:
```python
# Record execution
if metaprogramming:
    record_task_execution(
        metaprogramming,
        task_description=task,
        success=result.success,
        cost_tokens=result.tokens_used,
        iterations_used=result.tool_calls,
        tools_used=result.tools_called,
        execution_time_seconds=result.duration
    )
```

### In Agent Runtime (`run_agent.py`)

During agent initialization:
```python
# Setup metaprogramming
self.metaprogramming = setup_metaprogramming(self)
```

During conversation loop:
```python
# Check for capability gaps
gaps = self.metaprogramming.detect_capability_gaps(task)
if gaps:
    logger.warning("Detected gaps: %s", gaps)

# Propose self-improvements
if success and child_agent:
    proposal_id = self.metaprogramming.propose_parent_improvement(...)
```

### Via Skills or Commands

Users can query agent introspection:
```python
# /introspect - show self-config
# /capabilities - show what agent can do
# /genealogy - show agent lineage
# /improvements - show proposed modifications
```

## Database Storage

Two SQLite databases in `~/.hercules/meta/`:

### `architecture_registry.db`
- Stores task-agent pairings and success rates
- Indexed by task type, model, success
- Supports similarity lookups

### `emergence_tracker.db`
- Stores agent genealogy information
- Tracks agent lineage and relationships
- Records emergence events

## Success Criteria

✓ **Agents can introspect**: Query own config, tools, performance
✓ **Registry captures success**: >90% of successful task-agent pairings logged
✓ **Reuse improves success**: Reused architectures boost success rate 30%+
✓ **Child agents are more efficient**: Agent B designed by A costs 50% less than human-designed
✓ **Emergence is detected**: System identifies agents discovering new capabilities
✓ **All code compiles**: No regressions, full integration
✓ **Genealogy is traceable**: Who designed this agent and how

## Data Flow

```
Task Execution
    ↓
Record in Registry
    ↓
Infer Task Type
    ↓
Lookup Similar Successes
    ↓
Detect Emergence Patterns
    ↓
Propose Improvements
    ↓
Spawn Optimized Child
    ↓
Loop
```

## Example: Complete Workflow

```python
# 1. Parent agent initializes
parent = AIAgent(model="claude-opus")
metaprog = setup_metaprogramming(parent)

# 2. Parent receives task
task = "Build microservices deployment pipeline"

# 3. Parent designs optimized child
child_config = metaprog.design_subagent_config(task)
# Returns: model=opus, tools=[bash,code], iterations=25

# 4. Parent spawns child with design
child = spawn_subagent(task, config=child_config)

# 5. Child executes and succeeds
result = child.run_conversation(task)

# 6. Parent records execution
task_id = record_task_execution(
    metaprog,
    task_description=task,
    success=True,
    cost_tokens=4200,
    iterations_used=18,
    tools_used=["bash", "code"],
    execution_time_seconds=62.5
)

# 7. Child proposes improvement
proposal = metaprog.propose_parent_improvement(
    task_description=task,
    delta_config={"max_iterations": 30},
    expected_improvement={"success_rate": 0.1},
    justification="Could benefit from more iteration budget"
)

# 8. Parent reviews and accepts
verdict = parent.metaprogramming.self_modifier.review_proposal(proposal)

# 9. System records emergence
genealogy = AgentGenealogy(
    agent_id=child.session_id,
    parent_agent_id=parent.session_id,
    generation=1,
    capabilities_gained=["deployment_optimization"],
    emergence_score=0.35
)
metaprog.emergence.record_agent_genealogy(genealogy)

# 10. Next similar task uses design from registry
next_task = "Deploy Kubernetes cluster"
next_config = registry.lookup_successful_architecture(next_task)
# Returns: configuration similar to what child discovered
```

## Testing

Run the comprehensive test suite:
```bash
python -m pytest tests/test_agent_meta_architecture.py -v
```

Tests cover:
- Introspection API
- Design API  
- Registry operations
- Emergence detection
- Self-modification
- Task-aware design
- End-to-end integration

## Future Enhancements

1. **Semantic embeddings**: Use LLM embeddings for better task similarity
2. **Proof verification**: Integrate consensus proofs for modification validation
3. **Multi-agent learning**: Share architectures across agent fleet
4. **Adaptive budgets**: Adjust resource limits based on task complexity
5. **Capability composition**: Combine learned capabilities into new abilities
6. **Genealogy visualization**: UI for exploring agent family trees
