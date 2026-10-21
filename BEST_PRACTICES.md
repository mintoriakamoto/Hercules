# Hercules: Best Practices for World-Class Coding Agent

## Architecture Principles

### 1. **Tiered Dependency Management**
- Core tier: Zero optional dependencies
- Execution tier: Only fast inference and tool orchestration
- Gateway tier: Optional platform integrations
- Prevents entire system failure from missing packages

### 2. **Code Understanding First**
Always analyze code structure before modification:
- Use AST parsing for complete code understanding
- Build dependency graphs
- Calculate cyclomatic complexity
- Identify related files automatically

```python
from agent.code_understanding import CodeRepository
repo = CodeRepository()
related = repo.find_related_files("target.py", depth=2)
```

### 3. **Tree-of-Thought Planning**
For complex tasks, explore multiple solution paths:
```python
from agent.planning.tree_of_thought import TreeOfThought

planner = TreeOfThought(
    initial_state="implement feature X",
    evaluator=lambda x: score_approach(x),
    generator=lambda x: generate_alternatives(x),
)
solutions = await planner.explore()
```

### 4. **Context Optimization**
Never exceed token limits - use intelligent context windows:
```python
from agent.context_optimization import ContextWindow

window = ContextWindow(
    max_tokens=4000,
    window_strategy="sliding_relevance"
)
window.add_item(code, "code", importance="high")
context = window.get_context()  # Automatically trimmed
```

### 5. **Error Recovery**
Never fail silently - diagnose and recover:
```python
from agent.error_recovery import ErrorRecovery

recovery = ErrorRecovery()
try:
    do_something()
except Exception as e:
    diagnosis = recovery.diagnose(e)
    if diagnosis.severity == ErrorSeverity.CRITICAL:
        raise
    recovery.attempt_recovery(diagnosis)
```

### 6. **Performance Tracking**
Measure everything:
```python
from agent.performance_analytics import PerformanceTracker

tracker = PerformanceTracker()
tracker.record_operation("code_generation", 250.5, 1500, "claude-sonnet")
stats = tracker.get_operation_stats("code_generation")
# Shows: avg latency, P95, success rate, cost
```

### 7. **Autonomy Control**
Respect resource limits and approval gates:
```python
from agent.autonomy_control import AutonomyController, AutonomyLevel

controller = AutonomyController(AutonomyLevel.SEMI_AUTO)
if controller.can_execute("delete_file.py"):
    delete_file()
```

## Implementation Strategy

### Phase 1: Understanding (40% of time)
1. Analyze codebase structure
2. Identify affected files
3. Understand existing patterns
4. Map dependencies

### Phase 2: Planning (30% of time)
1. Generate multiple approaches
2. Evaluate tradeoffs
3. Build step-by-step plan
4. Identify risks and mitigations

### Phase 3: Execution (20% of time)
1. Execute minimal, focused changes
2. Test immediately
3. Verify against requirements
4. Document decisions

### Phase 4: Validation (10% of time)
1. Run full test suite
2. Check performance impact
3. Verify no regressions
4. Gather metrics

## Quality Standards

### Code Review Checklist
- [ ] Uses appropriate architecture pattern
- [ ] Follows project conventions
- [ ] Has comprehensive error handling
- [ ] Includes tests
- [ ] Performance acceptable
- [ ] No unnecessary complexity
- [ ] Documented (if needed)
- [ ] Backward compatible

### Performance Targets
- **Code understanding**: <500ms for 10K LOC file
- **Planning**: <2s for complex tasks
- **Execution**: <5s per atomic change
- **Testing**: <30s for 100-test suite
- **Context**: <4K tokens average usage

### Cost Optimization
- Use Claude Haiku for simple tasks (<1K tokens)
- Use Claude Sonnet for complex tasks
- Cache analysis results aggressively
- Batch operations when possible

## Common Patterns

### Pattern 1: Safe File Modification
```python
# 1. Understand
analyzer = CodeAnalyzer(filepath)

# 2. Plan
changes = plan_modifications(analyzer)

# 3. Execute (test first)
test_change(changes)
apply_change(changes)

# 4. Validate
verify_no_regressions()
```

### Pattern 2: Feature Implementation
```python
# 1. Analyze related code
repo = CodeRepository()
related = repo.find_related_files(target)

# 2. Multi-path exploration
planner = TreeOfThought(task, evaluator, generator)
approaches = await planner.explore()

# 3. Execute best approach
for step in approaches[0]:
    execute_step(step)
    test_step()
```

### Pattern 3: Error Resolution
```python
while attempts < 3:
    try:
        perform_task()
        break
    except Exception as e:
        diagnosis = recovery.diagnose(e)
        if not recovery.attempt_recovery(diagnosis):
            raise
        attempts += 1
```

## Tools Integration

### Use for Every Task
- **CodeAnalyzer**: Understand code structure
- **PerformanceTracker**: Measure operations
- **AutonomyController**: Check resource limits
- **ErrorRecovery**: Handle failures gracefully

### Conditional Integration
- **TreeOfThought**: Multi-step planning
- **ContextWindow**: Large codebases
- **CapabilitiesRegistry**: Learning from history

## Competitive Advantages

1. **Deep Code Understanding** - AST analysis + dependency graphs
2. **Multi-Path Planning** - Tree-of-thought vs single path
3. **Intelligent Context** - Sliding window with relevance scoring
4. **Graceful Degradation** - Comprehensive error recovery
5. **Performance Tracking** - Know what works, optimize continually
6. **Safety First** - Autonomy limits, approval gates
7. **Cost Aware** - Model selection, token optimization
8. **Learning System** - Capability registry, pattern matching

## Success Metrics

Track these across projects:
- Code understanding accuracy: 95%+
- Plan quality (evaluator score): 85%+
- First-try success rate: 80%+
- Performance vs target: 100%+
- Cost per operation: 50% below baseline
- Regression rate: 0%
- User satisfaction: 90%+

## References

See modules in `agent/`:
- `code_understanding.py` - Deep analysis
- `planning/tree_of_thought.py` - Advanced planning
- `context_optimization.py` - Smart windowing
- `error_recovery.py` - Self-healing
- `performance_analytics.py` - Metrics
- `autonomy_control.py` - Safety
- `capabilities_registry.py` - Learning

For integration examples, see `INTEGRATION_GUIDE.md`.
