# Architecture as Code: Usage Guide

## Quick Start

### Enable Architecture-as-Code in Your Agent

```python
from run_agent import AIAgent
from agent.meta.integration import setup_metaprogramming

# Create agent
agent = AIAgent(model="claude-opus-4-20250514")

# Enable metaprogramming
metaprog = setup_metaprogramming(agent)

# Now agent can introspect, design, and learn!
```

## Basic Operations

### 1. Agent Self-Awareness

**Check what the agent can do:**

```python
from agent.meta.introspection import Introspection

introspect = Introspection(agent)

# Get complete configuration
config = introspect.get_self_config()
print(f"Model: {config.model}")
print(f"Toolsets: {config.toolsets}")
print(f"Max iterations: {config.max_iterations}")

# List capabilities
capabilities = introspect.query_self_capabilities()
print(f"Available tools: {capabilities.tools}")
print(f"Success rate: {capabilities.success_rate:.1%}")
print(f"Average cost: {capabilities.avg_cost_per_task:.0f} tokens")

# Identify capability gaps
gaps = introspect.estimate_capability_gap(
    "Design a complex distributed system with formal verification"
)
for gap in gaps:
    print(f"- {gap.gap_type}: {gap.recommended_solution}")
```

### 2. Learning from Task Execution

**Record what happens after each task:**

```python
from agent.meta.integration import record_task_execution

# After task completes
task_id = record_task_execution(
    metaprog,
    task_description="Implement WebSocket server with tests",
    success=True,
    cost_tokens=3500,
    iterations_used=12,
    tools_used=["bash", "code", "files"],
    execution_time_seconds=45.2
)

print(f"Recorded task {task_id}")

# Check performance metrics
metrics = metaprog.get_performance_metrics()
print(f"Success rate: {metrics['overall_success_rate']:.1%}")
print(f"Avg cost: {metrics['avg_cost_tokens']:.0f} tokens/task")
print(f"Total tasks: {metrics['total_tasks']}")
```

### 3. Designing Specialized Agents

**Before spawning a subagent, design it for the task:**

```python
from agent.meta.integration import design_subagent

task = "Optimize database queries for large-scale data processing"

# Design optimized agent
subagent_config = design_subagent(metaprog, task)

print(f"Model: {subagent_config['model']}")
print(f"Tools: {subagent_config['enabled_toolsets']}")
print(f"Max iterations: {subagent_config['max_iterations']}")

# Use config when spawning
child_agent = AIAgent(
    model=subagent_config['model'],
    enabled_toolsets=subagent_config['enabled_toolsets'],
    max_iterations=subagent_config['max_iterations'],
    ...
)

# Execute with specialized config
result = child_agent.run_conversation(task)
```

### 4. Detecting Capability Gaps

**Identify what's missing:**

```python
# Check what gaps exist for a new task
gaps = metaprog.detect_capability_gaps(
    "Research novel cryptographic proofs and implement them"
)

for gap in gaps:
    print(f"\n{gap['type'].upper()}")
    print(f"  Issue: {gap['description']}")
    print(f"  Fix: {gap['recommendation']}")
    print(f"  Priority: {gap['priority']}/5")
    print(f"  Impact: {gap['impact']:.1%} on success")
```

### 5. Child Agent Proposes Improvements

**Subagent proposes configuration changes to parent:**

```python
# After child succeeds on difficult task
proposal_id = metaprog.propose_parent_improvement(
    task_description="Process 100GB log file and identify patterns",
    delta_config={
        "max_iterations": 40,  # Need more iterations
        "max_tokens": 12000,   # Need larger context
        "enabled_toolsets": ["code", "bash", "files"]
    },
    expected_improvement={
        "success_rate": 0.15,  # 15% improvement
        "cost": -0.05  # 5% cost reduction
    },
    justification="Larger iteration budget allows better exploration for large-scale tasks"
)

print(f"Proposed modification: {proposal_id}")

# Parent will review and accept/reject based on validation
```

### 6. Tracking Agent Lineage

**Understand agent genealogy:**

```python
# Get agent's family tree
genealogy = metaprog.get_agent_genealogy()
print(f"Agent generation: {genealogy['generation']}")
print(f"Parent: {genealogy['parent_id']}")
print(f"Capabilities gained: {genealogy['capabilities_gained']}")
print(f"Emergence score: {genealogy['emergence_score']:.2f}/1.0")

# Get who designed this agent
designer = genealogy.get('designed_by')
if designer:
    print(f"Designed by: {designer}")
```

### 7. Registry Lookups

**Reuse proven architectures:**

```python
from agent.meta.registry import ArchitectureRegistry

registry = ArchitectureRegistry()

# Get architecture proven successful for similar task
similar_config = registry.lookup_successful_architecture(
    "Build REST API with FastAPI and SQLAlchemy"
)

if similar_config:
    print("Found similar successful architecture!")
    print(f"Model: {similar_config['model']}")
    print(f"Tools: {similar_config['enabled_toolsets']}")
else:
    print("No similar task found in registry")

# Get statistics
stats = registry.get_statistics()
print(f"\nRegistry statistics:")
print(f"  Total records: {stats['total_records']}")
print(f"  Success rate: {stats['overall_success_rate']:.1%}")
print(f"  Most common models: {[m['model'] for m in stats['top_models']]}")
```

## Advanced Usage

### Complete Delegation Workflow

```python
from agent.meta.integration import setup_metaprogramming, design_subagent, record_task_execution

# Parent setup
parent = AIAgent(model="claude-opus-4-20250514")
parent_metaprog = setup_metaprogramming(parent)

# Task to delegate
task = "Build machine learning pipeline for classification"

# Step 1: Design optimized child
child_config = design_subagent(parent_metaprog, task)

# Step 2: Spawn child with optimized config
child = AIAgent(
    model=child_config['model'],
    enabled_toolsets=child_config['enabled_toolsets'],
    max_iterations=child_config['max_iterations'],
    parent_session_id=parent.session_id  # Track lineage
)

# Child setup metaprogramming
child_metaprog = setup_metaprogramming(child)

# Step 3: Child executes task
result = child.run_conversation(task)

# Step 4: Record execution
task_id = record_task_execution(
    parent_metaprog,
    task_description=task,
    success=result.success,
    cost_tokens=result.tokens_used,
    iterations_used=result.tool_calls,
    tools_used=result.tools_called,
    execution_time_seconds=result.duration
)

# Step 5: Child proposes improvements if learned something
if result.success and result.tokens_used < expected_cost * 0.8:
    # Child discovered efficiency improvement
    proposal_id = child_metaprog.propose_parent_improvement(
        task_description=task,
        delta_config={
            "max_iterations": child_config['max_iterations'] - 5,
            "max_tokens": child_config.get('max_tokens', 4096) - 1000
        },
        expected_improvement={
            "cost": -0.2  # Can run with 20% less budget
        },
        justification="Efficient solution discovered, lower budget sufficient"
    )

    # Parent reviews
    verdict = parent_metaprog.self_modifier.review_proposal(proposal_id)
    if verdict.accepted:
        print("Child's improvement accepted by parent")
```

### Emergence Detection

```python
from agent.meta.emergence import EmergenceTracker

tracker = EmergenceTracker()

# Record parent and child agents
parent_gen = AgentGenealogy(
    agent_id="parent-v1",
    parent_agent_id=None,
    generation=0,
    design_timestamp=time.time(),
    capabilities_gained=[],
    capabilities_lost=[],
    emergence_score=0.0
)
tracker.record_agent_genealogy(parent_gen)

# Child discovers new capability
child_gen = AgentGenealogy(
    agent_id="child-v1",
    parent_agent_id="parent-v1",
    generation=1,
    design_timestamp=time.time(),
    capabilities_gained=["advanced_bash_scripting", "parallel_processing"],
    capabilities_lost=[],
    emergence_score=0.0  # Will be updated
)
tracker.record_agent_genealogy(child_gen)

# Detect emergence signals
parent_tools = ["core", "bash", "code"]
child_tools = ["core", "bash", "code", "advanced_bash_extension"]

events = tracker.detect_emergence(
    agent_id="child-v1",
    parent_agent_id="parent-v1",
    new_capabilities=child_tools,
    parent_capabilities=parent_tools,
    performance_vs_parent={
        "parent_avg_cost": 2500,
        "child_avg_cost": 1800,
        "parent_success_rate": 0.72,
        "child_success_rate": 0.89
    }
)

print(f"Detected {len(events)} emergence signals:")
for event in events:
    print(f"  - {event.event_type}: {event.description} (impact {event.impact_score:.2f})")

# Get agents at emergence frontier
frontier = tracker.get_emergence_frontier()
print(f"\nAgents with highest emergence:")
for agent_id, score in frontier[:5]:
    print(f"  {agent_id}: {score:.2f}")
```

### Analyzing Task Types

```python
from agent.planning.task_designer import TaskDesigner

designer = TaskDesigner()

task = "Design a secure microservices architecture with service-to-service authentication"

# Analyze task
analysis = designer._analyze_task(task)

print(f"Task type: {analysis.task_type}")
print(f"Complexity: {analysis.complexity_score:.1%}")
print(f"Estimated tokens: {analysis.estimated_tokens}")
print(f"Estimated iterations: {analysis.estimated_iterations}")
print(f"Required tools: {analysis.required_tools}")
print(f"Required models: {analysis.required_models}")
print(f"Parallelizable: {analysis.parallelizable}")
print(f"Needs verification: {analysis.requires_verification}")
print(f"Estimated time: {analysis.estimated_time_minutes:.1f} minutes")

# Design blueprint
blueprint = designer.design_agent_for_task(task)
print(f"\nOptimized agent:")
print(f"  Model: {blueprint.model}")
print(f"  Tools: {blueprint.toolsets}")
print(f"  Iterations: {blueprint.max_iterations}")
print(f"  Success rate estimate: {blueprint.estimated_success_rate:.1%}")
print(f"  Cost estimate: {blueprint.estimated_cost_tokens:.0f} tokens")
```

## Integration with Hercules

### In Agent Initialization

```python
# hercules_cli/main.py or entry point
def create_agent_with_metaprogramming():
    agent = AIAgent(
        model=args.model,
        enabled_toolsets=args.toolsets,
        ...
    )
    
    # Setup metaprogramming
    if args.enable_architecture_as_code:
        agent.metaprogramming = setup_metaprogramming(agent)
        logger.info("Architecture-as-code enabled")
    
    return agent
```

### In Delegation

```python
# tools/delegate_tool.py
def _build_child_agent(parent_agent, task_description, ...):
    # Design child configuration
    if hasattr(parent_agent, 'metaprogramming'):
        child_config = parent_agent.metaprogramming.design_subagent_config(
            task_description
        )
        # Use designed config for child
        model = child_config.get('model', parent_agent.model)
        toolsets = child_config.get('enabled_toolsets', parent_agent.enabled_toolsets)
    else:
        # Fallback to parent config
        model = parent_agent.model
        toolsets = parent_agent.enabled_toolsets
    
    # Create child with optimized config
    child = AIAgent(
        model=model,
        enabled_toolsets=toolsets,
        parent_session_id=parent_agent.session_id,
        ...
    )
    
    return child
```

### In Conversation Loop

```python
# agent/conversation_loop.py
def record_task_completion(agent, task_description, success, metrics):
    if hasattr(agent, 'metaprogramming'):
        record_task_execution(
            agent.metaprogramming,
            task_description=task_description,
            success=success,
            cost_tokens=metrics['tokens'],
            iterations_used=metrics['tool_calls'],
            tools_used=metrics['tools'],
            execution_time_seconds=metrics['duration']
        )
```

## Monitoring and Debugging

### View Agent Status

```python
# Get complete metaprogramming state
state = metaprog.export_state()

print("Agent Configuration:")
pprint(state['agent_config'])

print("\nCapabilities:")
pprint(state['capabilities'])

print("\nPerformance Metrics:")
pprint(state['performance_metrics'])

print("\nGenealogy:")
pprint(state['genealogy'])

print("\nPending Modifications:")
for proposal_id, proposal in state['pending_modifications'].items():
    print(f"  {proposal_id}: {proposal['justification']}")
```

### Check Emergence Progress

```python
# Get evolution timeline
frontier = metaprog.emergence.get_emergence_frontier()
print("Top emergence agents:")
for agent_id, score in frontier:
    lineage = metaprog.emergence.get_agent_lineage(agent_id)
    gen = lineage[0]
    print(f"  {agent_id}")
    print(f"    Generation: {gen.generation}")
    print(f"    Emergence: {score:.2f}/1.0")
    print(f"    New capabilities: {gen.capabilities_gained}")
```

### Database Inspection

```python
import sqlite3

# Query architecture registry
with sqlite3.connect(registry.db_path) as conn:
    cursor = conn.execute(
        "SELECT task_type, AVG(success_rate) as avg_success, COUNT(*) "
        "FROM architecture_records "
        "WHERE success = 1 "
        "GROUP BY task_type "
        "ORDER BY avg_success DESC"
    )
    
    print("Success rates by task type:")
    for task_type, avg_success, count in cursor:
        print(f"  {task_type}: {avg_success:.1%} ({count} records)")
```

## Best Practices

1. **Record consistently**: Log every significant task execution
2. **Use task types**: Classify tasks so similar ones can be grouped
3. **Review proposals**: Parent agents should review child modifications
4. **Monitor emergence**: Track which agents are creating new capabilities
5. **Clean old records**: Periodically purge records older than 30 days
6. **Export state regularly**: Save agent state snapshots for analysis
7. **Test designs**: Verify optimized agents work before production use

## Troubleshooting

**Q: Registry not finding similar tasks?**
A: Task descriptions need sufficient keywords. Try using domain-specific terminology.

**Q: Emergence not detected?**
A: Make sure performance metrics are significantly different (>10-20%). Small improvements may not trigger detection.

**Q: Self-modification proposals being rejected?**
A: Verify expected improvements are realistic (0.1-0.3 range). Too-aggressive proposals fail validation.

**Q: High registry database size?**
A: Run `registry.clear_old_records(days=30)` periodically to clean up old entries.
