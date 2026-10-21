# Integration Guide: Advanced Agent Capabilities

## Quick Start: 5-Minute Setup

### Step 1: Import the Advanced Agent
```python
from agent.advanced_agent import AdvancedCodingAgent
from agent.autonomy_control import AutonomyLevel

# Create agent with semi-autonomous mode
agent = AdvancedCodingAgent(autonomy_level=AutonomyLevel.SEMI_AUTO)
```

### Step 2: Understand the Codebase
```python
# Analyze target file and related code
analysis = agent.understand_codebase("target_file.py")
print(f"Related files: {analysis['related_files']}")
print(f"Complexity: {analysis['complexity']}")
```

### Step 3: Plan Implementation
```python
# Generate multiple approaches
approaches = await agent.plan_implementation(
    task="Add caching to slow function",
    context=agent.get_execution_context(),
    num_approaches=3
)

for i, approach in enumerate(approaches, 1):
    print(f"Approach {i}: {approach}")
```

### Step 4: Execute and Track
```python
success, error = agent.execute_task(
    "Implement caching decorator",
    task_fn=lambda: implement_caching(),
)

print(f"Success: {success}, Error: {error}")
print(f"Agent Status: {agent.get_agent_status()}")
```

---

## Advanced: Full Workflow

### Task 1: Deep Code Analysis
```python
from agent.code_understanding import CodeRepository

repo = CodeRepository(root=Path("."))

# Find all files related to target
related = repo.find_related_files("core/inference.py", depth=3)

# Get complexity report
report = repo.get_complexity_report()
print(f"Most complex files: {report['most_complex_files']}")
```

### Task 2: Multi-Path Planning
```python
from agent.planning.tree_of_thought import TreeOfThought

def score_approach(approach: str) -> float:
    score = 0.5
    if "simple" in approach: score += 0.2
    if "async" in approach: score += 0.3
    if "test" in approach: score += 0.2
    return min(1.0, score)

def generate_next(current: str) -> list:
    return [
        f"{current} with async/await",
        f"{current} with threading",
        f"{current} with multiprocessing",
    ]

planner = TreeOfThought(
    initial_state="Parallelize data processing",
    evaluator=score_approach,
    generator=generate_next,
    max_depth=4,
    beam_width=3,
)

solutions = await planner.explore()
print(f"Solutions found: {planner.visualize()}")
```

### Task 3: Context Management
```python
from agent.context_optimization import ContextWindow

# Create intelligent window
window = ContextWindow(
    max_tokens=4000,
    reserve_tokens=1000,  # Keep for response
    window_strategy="sliding_relevance"
)

# Add context items
window.add_item(code_snippet, "code", importance="high")
window.add_item(error_message, "error", importance="critical")
window.add_item(plan, "plan", importance="medium")

# Get optimized context
context = window.get_context()
print(f"Used {window.total_tokens} / {window.available_tokens} tokens")
```

### Task 4: Error Handling & Recovery
```python
from agent.error_recovery import ErrorRecovery, ErrorSeverity

recovery = ErrorRecovery()

for attempt in range(3):
    try:
        perform_risky_operation()
        break
    except Exception as e:
        diagnosis = recovery.diagnose(e)
        
        print(f"Error: {diagnosis.category.value}")
        print(f"Severity: {diagnosis.severity.value}")
        print(f"Suggestions: {diagnosis.recovery_suggestions}")
        
        if diagnosis.severity == ErrorSeverity.CRITICAL:
            raise
        
        if not recovery.attempt_recovery(diagnosis):
            print(f"Recovery failed: {recovery.get_failure_report()}")
            break
```

### Task 5: Performance Tracking
```python
from agent.performance_analytics import PerformanceTracker

tracker = PerformanceTracker()

# Record operations
for operation in operations:
    start = time.time()
    result = perform_operation(operation)
    latency = (time.time() - start) * 1000
    
    tracker.record_operation(
        operation="code_modification",
        latency_ms=latency,
        tokens_used=estimate_tokens(result),
        model="claude-sonnet",
        success=True,
    )

# Analyze
stats = tracker.get_operation_stats("code_modification")
print(f"Avg latency: {stats['avg_latency_ms']:.1f}ms")
print(f"Success rate: {stats['success_rate']:.1%}")
print(f"Cost per operation: ${stats['avg_cost_per_op']:.4f}")
```

### Task 6: Autonomy & Safety
```python
from agent.autonomy_control import AutonomyController, AutonomyLevel, ResourceLimits

limits = ResourceLimits(
    max_api_calls=100,
    max_tokens_per_call=4000,
    max_file_writes=50,
    max_cost_usd=5.0,
)

controller = AutonomyController(
    level=AutonomyLevel.SEMI_AUTO,
    limits=limits,
)

# Set approval callback
def approve_operation(operation: str) -> bool:
    print(f"Request approval for: {operation}")
    return input("Approve? (y/n): ").lower() == 'y'

controller.set_approval_fn(approve_operation)

# Check before execution
if controller.can_execute("Delete temporary files"):
    delete_temp_files()
else:
    print("Operation not approved or resource limits exceeded")
    print(controller.get_status())
```

### Task 7: Learning & Adaptation
```python
from agent.capabilities_registry import CapabilitiesRegistry, Capability, CapabilityType

registry = CapabilitiesRegistry()

# Register capabilities
registry.register_capability(Capability(
    name="code_generation",
    type=CapabilityType.EXECUTION,
    description="Generate new code",
    best_for=["feature", "implementation"],
))

# Record task execution
registry.record_task(
    task_description="Add validation function",
    capabilities_used=["code_understanding", "code_generation", "testing"],
    success=True,
    latency_ms=2400,
    insights="Simpler approach was faster",
)

# Learn from history
profile = registry.get_capability_profile()
print(f"Success rate: {profile['success_rate']:.1%}")
print(f"Strongest capabilities: {profile['strongest_capabilities']}")

improvements = registry.suggest_capability_improvement()
for suggestion in improvements:
    print(f"Consider: {suggestion}")
```

---

## Integration Patterns

### Pattern 1: Complete Task Workflow
```python
async def solve_coding_task(task_description: str):
    agent = AdvancedCodingAgent(AutonomyLevel.HUMAN_PLUS)
    
    # Step 1: Understand
    print("📚 Analyzing codebase...")
    analysis = agent.understand_codebase("target.py")
    
    # Step 2: Plan
    print("🧠 Planning approaches...")
    approaches = await agent.plan_implementation(
        task=task_description,
        context=agent.get_execution_context(),
    )
    
    # Step 3: Add context
    print("📝 Preparing context...")
    for doc in get_relevant_docs(task_description):
        agent.add_context(doc, "reference")
    
    # Step 4: Execute
    print("⚙️ Executing...")
    success, error = agent.execute_task(
        task_description,
        task_fn=implement_solution,
    )
    
    # Step 5: Report
    print("📊 Results:")
    status = agent.get_agent_status()
    print(json.dumps(status, indent=2))
    
    return success
```

### Pattern 2: Batch Processing
```python
async def batch_code_improvements(files: list):
    agent = AdvancedCodingAgent(AutonomyLevel.FULL_AUTO)
    tracker = PerformanceTracker()
    
    for filepath in files:
        print(f"Processing {filepath}...")
        
        success, _ = agent.execute_task(
            f"Improve {filepath}",
            task_fn=lambda f=filepath: improve_file(f),
        )
        
        if success:
            tracker.record_operation(
                "file_improvement",
                100,  # estimated latency
                1000,  # estimated tokens
                "claude-haiku",
            )
    
    # Summary
    stats = tracker.get_model_comparison()
    print(json.dumps(stats, indent=2))
```

---

## Monitoring & Debugging

### View Agent Metrics
```python
status = agent.get_agent_status()

print(f"Tasks completed: {status['tasks_completed']}")
print(f"Autonomy level: {status['autonomy']['level']}")
print(f"Remaining budget:")
print(f"  - API calls: {status['autonomy']['remaining']['api_calls']}")
print(f"  - Cost: ${status['autonomy']['remaining']['cost_usd']:.2f}")
print(f"\nCapabilities:")
for cap, data in status['capabilities']['capabilities'].items():
    print(f"  {cap}: {data['success_rate']:.1%} success rate")
```

### Export Performance Data
```python
tracker.export_metrics("metrics.json")
# Inspect with: cat metrics.json | jq .summary
```

### Visualize Planning Tree
```python
planner = TreeOfThought(...)
solutions = await planner.explore()
print(planner.visualize())

# Example output:
# 🔍 Task: Implement caching... ()
# ├── ⭐ With LRU cache... (0.85)
# │   ├── ✓ Test coverage... (0.95)
# │   └── ✓ Documentation... (0.90)
# └── 🔍 With Redis... (0.65)
```

---

## Performance Targets

When integrated, Hercules should achieve:

| Metric | Target | Status |
|--------|--------|--------|
| Code understanding | <500ms | ✓ Implemented |
| Planning | <2s for complex | ✓ Implemented |
| Context optimization | <4K tokens | ✓ Implemented |
| Error recovery | <500ms | ✓ Implemented |
| Performance tracking | <1ms overhead | ✓ Implemented |
| Autonomy checks | <10ms | ✓ Implemented |

---

## Troubleshooting

### "Exceeds token limit"
→ Use `ContextWindow` with `sliding_relevance` strategy

### "Execution not approved"
→ Check `autonomy.get_status()` for remaining budget

### "Error recovery failed"
→ Check `error_recovery.get_failure_report()`

### "Slow code understanding"
→ Use `CodeRepository.find_related_files()` to limit scope

---

## Next Steps

1. Read `BEST_PRACTICES.md` for implementation patterns
2. Review `agent/advanced_agent.py` for full integration
3. Run examples in `tests/` directory
4. Monitor with performance analytics

For questions, see module docstrings in `agent/`.
