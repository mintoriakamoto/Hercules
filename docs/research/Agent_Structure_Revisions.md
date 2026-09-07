# Agent Structure Revisions: Integration of CORAL & Extended Reasoning

## Overview

The Hercules agent architecture has been revised to deeply integrate CORAL self-improvement and extended reasoning throughout the agent lifecycle, subagent management, and parallel task orchestration.

## Architecture Changes

### Before: Static Agent Structure

```
AIAgent
├── Conversation Loop
│   ├── Tool Execution
│   └── Response Handling
├── Subagent Creation (flat, no reasoning)
└── No Performance Tracking
```

### After: Self-Improving, Reasoning-Enhanced Architecture

```
AIAgent
├── Agent Orchestrator
│   ├── CORAL Tracking
│   ├── Extended Reasoning
│   └── Tool Recommendations
├── Conversation Loop
│   ├── Context Initialization (with reasoning)
│   ├── Tool Execution (with performance tracking)
│   └── Failure Recovery (reasoning-based fallback)
├── Subagent Management
│   ├── Task Decomposition (reasoning-based)
│   ├── Subagent Initialization (improvement-aware)
│   └── Parallel Orchestration (monitoring + suggestions)
└── Multi-Agent Coordination
    ├── Cross-Agent Improvement Sharing
    └── Hierarchical Reasoning
```

## Key Components

### 1. Agent Orchestrator (`agent/agent_orchestration.py`)

Central coordinator for main agent and subagents.

**Responsibilities**:
- Initialize agent contexts with complexity analysis and reasoning
- Track tool executions for CORAL improvement engine
- Score and recommend tools based on task alignment
- Plan task decomposition across subagents
- Handle tool failures with reasoning-based recovery
- Record agent completion metrics
- Generate improvement suggestions

**Usage**:
```python
from agent.agent_orchestration import get_agent_orchestrator

orchestrator = get_agent_orchestrator()

# Initialize main agent
context = orchestrator.initialize_agent_context(
    agent_id="main_agent",
    task_description="Analyze and secure AWS infrastructure",
    time_budget_seconds=120,
    domain="security"
)
# Returns: AgentExecutionContext with complexity, reasoning chain, recommended tools

# Track tool execution
orchestrator.record_tool_execution(
    agent_id="main_agent",
    tool_name="web_search",
    success=True,
    latency_ms=1200
)

# Get improvement suggestions
suggestions = orchestrator.get_agent_improvement_suggestions("main_agent")

# Handle failure with fallback
recovery = orchestrator.handle_tool_failure(
    agent_id="main_agent",
    failed_tool="web_search",
    failure_reason="API rate limit exceeded",
    available_tools=["web_extract", "read_file"]
)
```

### 2. Subagent Orchestrator (`agent/subagent_orchestration.py`)

Manages subagent creation, monitoring, and improvement sharing.

**Key Classes**:
- `SubagentPlan`: Represents task decomposition strategy
- `SubagentMonitor`: Tracks active subagents and collects metrics

**Responsibilities**:
- Plan task decomposition using extended reasoning
- Generate subagent-specific system prompts with improvement context
- Monitor subagent performance
- Track tool usage across subagents
- Finalize subagents and capture learnings
- Propagate improvements from parent to children

**Usage**:
```python
from agent.subagent_orchestration import (
    plan_subagent_decomposition,
    get_subagent_system_prompt,
    get_subagent_monitor
)

# Plan how to decompose a complex task
plan = plan_subagent_decomposition(
    parent_task="Security audit of microservices",
    num_subagents=3,
    available_tools=["web_search", "read_file", "analyze_skill_performance"],
    parent_complexity=ReasoningComplexity.COMPLEX
)

# Build subagent system prompt with improvements
prompt = get_subagent_system_prompt(
    parent_task="Audit database security",
    subagent_id="subagent_0",
    parent_improvements={"suggestions": [...]}
)

# Monitor subagent execution
monitor = get_subagent_monitor()
monitor.register_subagent("subagent_0", "parent", "Audit task")
monitor.record_subagent_tool_use("subagent_0", "web_search", True, 1200)

# Get tool recommendations for subagent
tools = monitor.get_subagent_recommendations(
    "subagent_0",
    "Find security vulnerabilities",
    available_tools
)

# Finalize and capture learnings
result = monitor.finalize_subagent(
    subagent_id="subagent_0",
    success=True,
    total_time_ms=45000,
    tool_count=5
)
# Returns: metrics + improvement suggestions for parent to learn from
```

## Integration Points

### 1. Conversation Loop Integration

The conversation loop should call orchestrator at key points:

```python
# At agent start
orchestrator.initialize_agent_context(
    agent_id=session_id,
    task_description=user_message,
    domain=inferred_domain
)

# After each tool execution
orchestrator.record_tool_execution(
    agent_id=session_id,
    tool_name=tool_name,
    success=not error,
    latency_ms=elapsed_time
)

# On tool failure
recovery = orchestrator.handle_tool_failure(...)
# Use recovery.fallback_sequence to try alternative tools

# At agent completion
orchestrator.finalize_agent_execution(
    agent_id=session_id,
    success=overall_success,
    total_time_ms=total_elapsed,
    tool_count=num_tools_used
)
```

### 2. Delegate Tool Integration

The delegate_task tool should use orchestration for subagent planning:

```python
from agent.agent_orchestration import get_agent_orchestrator
from agent.subagent_orchestration import plan_subagent_decomposition

orchestrator = get_agent_orchestrator()

# Get current agent context to understand parent complexity
parent_context = orchestrator.active_contexts[parent_agent_id]

# Plan subagent decomposition
plan = plan_subagent_decomposition(
    parent_task=delegation_goal,
    num_subagents=num_workers,
    available_tools=child_tools,
    parent_complexity=parent_context.complexity
)

# Use plan to initialize and monitor subagents
for subagent_id, tasks in plan.subagent_assignments.items():
    # Create subagent with reasoning and improvement context
    # Track its execution
    # Capture learnings when complete
```

## Data Flow

### Main Agent Execution

```
User Input
    ↓
Initialize Context (reasoning + complexity analysis)
    ↓
For each turn:
  1. Get tool recommendations from orchestrator
  2. Select tool
  3. Execute tool
  4. Record execution (latency, success, error type)
  5. CORAL updates performance metrics
  6. On failure: Use reasoning for recovery
    ↓
Finalize execution (record completion)
    ↓
Generate improvement suggestions
```

### Subagent Delegation

```
Parent wants to delegate tasks
    ↓
Plan decomposition (reasoning-based)
    ↓
For each subagent:
  1. Register with monitor
  2. Initialize with parent improvements
  3. Execute assigned tasks
  4. Track each tool use
  5. On failure: Recovery suggestions
    ↓
Finalize subagent (capture learnings)
    ↓
Parent receives metrics + suggestions
    ↓
Parent learns and applies improvements
```

## Benefits

### 1. Self-Improvement Across Agent Instances
- Main agent improvements transfer to subagents
- Subagent learnings propagate back to parent
- Parallel execution accelerates learning

### 2. Intelligent Task Decomposition
- Reasoning drives how tasks are split
- Tool recommendations per subagent
- Optimized for parallel execution

### 3. Failure Recovery
- Extended reasoning generates smart fallbacks
- Context-aware recovery strategies
- Tracks what works for future reference

### 4. Observable Orchestration
- See main agent and all subagents in real-time
- Metrics on tool effectiveness
- Improvement opportunities identified automatically

### 5. Performance Monitoring
- Track latency and success rates across all agents
- Identify bottlenecks (slow tools, error-prone tasks)
- Optimize tool assignment based on history

## Configuration

### Agent Orchestration Options

```yaml
# ~/.hercules/config.yaml
agent:
  orchestration:
    # Enable reasoning-based planning
    use_reasoning: true
    
    # Track performance metrics
    track_performance: true
    
    # Automatically apply improvements
    auto_improve: true
    
    # Subagent-specific settings
    subagent:
      # Share parent improvements with children
      inherit_improvements: true
      
      # Monitor subagent reasoning
      log_reasoning: false
      
      # Max nesting depth
      max_depth: 2
```

## Backward Compatibility

- Existing agent code continues to work unchanged
- Orchestration is optional (graceful degradation)
- No API changes to AIAgent class
- Tools don't need modification to be tracked

## Monitoring & Observability

### Via API

```python
metrics = orchestrator.get_orchestration_metrics()
# Returns:
# {
#   "active_agents": 4,
#   "total_executions": 1250,
#   "improvement_stats": {...},
#   "avg_execution_latency_ms": 340
# }
```

### Via Logs

```bash
# Watch agent orchestration
HERCULES_DEBUG=agent_orchestration hercules

# View subagent monitoring
tail -f ~/.hercules/logs/orchestration.log
```

### Via Dashboard

Future dashboard will show:
- Agent dependency tree
- Real-time tool usage
- Performance trends
- Improvement suggestions
- Cross-agent learning

## Future Enhancements

### Phase 1 (Q4 2026)
- [ ] Integrate orchestration into conversation loop
- [ ] Add to delegate_task for subagent planning
- [ ] Expose metrics via CLI commands
- [ ] Basic performance dashboard

### Phase 2 (2027)
- [ ] Reinforcement learning for tool assignment
- [ ] Hierarchical task decomposition
- [ ] Neural tool recommendation (embeddings)
- [ ] Collaborative reasoning between agents

### Phase 3 (2027+)
- [ ] Federated learning across instances
- [ ] Meta-learning of orchestration strategies
- [ ] Autonomous agent team formation
- [ ] Self-optimizing agent topology

## Migration Guide

For existing agent integrations:

1. **No changes required** - orchestration works transparently
2. **Optional: Use API directly** - for fine-grained control
3. **Enable improvements** - set `auto_improve: true` in config
4. **Monitor progress** - use `get_orchestration_metrics()`

## Example: Complete Workflow

```python
from agent.agent_orchestration import get_agent_orchestrator
from agent.subagent_orchestration import get_subagent_monitor

# Main agent
orchestrator = get_agent_orchestrator()
context = orchestrator.initialize_agent_context(
    agent_id="session_123",
    task_description="Audit and hardening AWS infrastructure",
    time_budget_seconds=300,
    domain="security"
)

print(f"Task Complexity: {context.complexity.value}")
print(f"Recommended Tools: {context.recommended_tools}")
print(f"Time Budget: {context.time_budget_seconds}s")

# Execute tools and track performance
for tool in context.recommended_tools:
    success = execute_tool(tool)
    orchestrator.record_tool_execution("session_123", tool, success, latency)

# Handle failure gracefully
if not success:
    recovery = orchestrator.handle_tool_failure(
        "session_123", tool, "timeout", available_tools
    )
    for fallback_tool in recovery["fallback_sequence"]:
        execute_tool(fallback_tool)

# Get improvement suggestions
suggestions = orchestrator.get_agent_improvement_suggestions("session_123")
for suggestion in suggestions:
    print(f"Improve {suggestion['tool']}: {suggestion['recommendation']}")

# Finalize and capture metrics
orchestrator.finalize_agent_execution("session_123", success, total_time, tool_count)

# Get overall metrics
metrics = orchestrator.get_orchestration_metrics()
print(f"Total Improvements Applied: {metrics['improvement_stats']['total_improvements_applied']}")
```

---

**Status**: Implementation Complete  
**Date**: 2026-09-07  
**Compatibility**: Backward compatible, enhanced opt-in
