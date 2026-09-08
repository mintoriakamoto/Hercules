# Task-Aware Model Routing

## Overview

Task-Aware Model Routing automatically selects the most appropriate model for delegated tasks based on task complexity, category, and cost constraints. This feature enables:

- **Cost Optimization**: Simple tasks route to cheaper, faster models (e.g., Haiku, GPT-4o mini)
- **Capability Matching**: Complex tasks route to more powerful models (e.g., Opus, o1)
- **Consistent Quality**: Security and research tasks always receive sufficient capability
- **Security**: Routing validates all inputs and enforces safety constraints

## How It Works

### Task Analysis

When you delegate a task without specifying an explicit model, Hercules analyzes the task in four dimensions:

1. **Complexity Analysis**: Determines if the task is SIMPLE, MODERATE, COMPLEX, or CRITICAL
   - Simple: straightforward information retrieval
   - Moderate: analysis and classification tasks
   - Complex: reasoning and design work
   - Critical: novel problem-solving, security analysis

2. **Category Identification**: Classifies the task into a category
   - **READ**: Information retrieval, file reading (keywords: read, list, get, find, retrieve)
   - **ANALYZE**: Analysis, summarization, classification (keywords: analyze, summary, classify)
   - **CODE**: Programming, code generation, debugging (keywords: code, write, implement, debug)
   - **REASONING**: Complex reasoning, planning, design (keywords: reason, think, plan, design)
   - **RESEARCH**: Deep research, exploration, investigation (keywords: research, explore, investigate)
   - **SECURITY**: Security testing, vulnerability analysis (keywords: security, penetr, exploit, vuln)

3. **Rule Matching**: Applies routing rules that consider both complexity and category
   - Rules are ranked by how well they match the task's characteristics
   - Security tasks get special priority to ensure sufficient capability

4. **Tier Selection**: Routes to one of four model tiers
   - **fast_cheap**: Haiku, GPT-4o mini (cost baseline: 1.0x)
   - **balanced**: Sonnet, GPT-4o (cost baseline: 3.5x)
   - **capable**: Opus, o1 (cost baseline: 7.0x)
   - **extended**: Opus with extended thinking, o1-pro (cost baseline: 10.0x)

### Example Routing

```
Task: "List all files in the /tmp directory"
→ Complexity: SIMPLE
→ Category: READ
→ Routed Tier: fast_cheap
→ Selected Model: claude-haiku-4-5
→ Cost Savings: 75% vs default balanced tier
```

```
Task: "Design a secure authentication system for a multi-tenant SaaS platform"
→ Complexity: CRITICAL
→ Category: REASONING
→ Security Constraint Applied: Category REASONING + CRITICAL → minimum CAPABLE tier
→ Routed Tier: capable
→ Selected Model: claude-opus-5
→ Cost Savings: None (full capability needed)
```

```
Task: "Review this code for security vulnerabilities"
→ Complexity: COMPLEX
→ Category: SECURITY
→ Security Constraint Applied: Category SECURITY → minimum CAPABLE tier
→ Routed Tier: capable (upgraded from original BALANCED)
→ Selected Model: claude-opus-5
→ Reasoning: Security tasks never route to insufficient capability
```

## Configuration

Task-aware routing is configured in `cli-config.yaml` under the `delegation.task_aware_routing` section:

```yaml
delegation:
  task_aware_routing:
    # Enable/disable routing (default: true)
    enabled: true
    
    # Confidence threshold [0.0-1.0]
    # When confidence is lower, falls back to parent model (default: 0.7)
    confidence_threshold: 0.7
    
    # Customize model mappings per deployment
    model_tiers:
      fast_cheap:
        - "claude-haiku-4-5-20251001"
        - "gpt-4o-mini"
      balanced:
        - "claude-sonnet-5"
        - "gpt-4o"
      capable:
        - "claude-opus-5"
        - "o1-mini"
      extended:
        - "claude-opus-5"
        - "o1"
    
    # Cost multipliers for savings estimation (reference: fast_cheap = 1.0)
    cost_multipliers:
      fast_cheap: 1.0
      balanced: 3.5
      capable: 7.0
      extended: 10.0
    
    # Task complexity thresholds [0.0-1.0]
    complexity_thresholds:
      simple_moderate: 0.3    # Below: SIMPLE, above: MODERATE
      moderate_complex: 0.65  # Below: MODERATE, above: COMPLEX
      complex_critical: 0.85  # Below: COMPLEX, above: CRITICAL
    
    # Category-based constraints
    category_overrides:
      security:
        min_tier: "capable"   # Security tasks always use capable or higher
      read:
        max_tier: "balanced"  # Simple read tasks don't need extended tier
```

## Usage in Delegation

### Automatic Routing (Default)

When you delegate a task without specifying a model, routing is applied automatically:

```python
# Using delegate_task tool
delegate_task(
    goal="Read and summarize the file /tmp/report.txt",
    # Model not specified → routing applies
)

# Routing decision:
# - Complexity: SIMPLE (straightforward file read)
# - Category: READ
# - Routed model: claude-haiku-4-5 (fast_cheap tier)
# - Cost savings: 75%
```

### Explicit Model Override

You can still specify an explicit model to bypass routing:

```python
delegate_task(
    goal="Analyze this complex research paper",
    model="claude-opus-5",  # Explicit model overrides routing
)

# Routing is skipped, task uses specified model
```

### Per-Task Models in Batch Mode

In batch delegation, you can override the model for specific tasks:

```python
delegate_task(
    tasks=[
        {
            "goal": "List files in /tmp",
            # No model specified → routing applies → fast_cheap tier
        },
        {
            "goal": "Analyze security vulnerabilities",
            "model": "claude-opus-5",  # Explicit override for this task
        },
        {
            "goal": "Write Python code",
            # No model specified → routing applies → balanced tier
        },
    ]
)

# Task 1: Routes to fast_cheap (READ category, SIMPLE complexity)
# Task 2: Uses explicit claude-opus-5 (bypasses routing)
# Task 3: Routes to balanced (CODE category, MODERATE complexity)
```

## Logging and Observability

Routing decisions are logged at INFO level with full details:

```
Task routing decision: task=Summarize the document... → model=claude-sonnet-5 
  (tier=balanced, complexity=moderate, category=analyze, confidence=0.85, savings=0.0%)

Routing cost optimization: estimated 75% cost savings by using claude-haiku-4-5
  (reasoning: Matched rule for simple read)

Security constraint applied: category=security enforces tier capable (was: balanced)
```

Debug logging (enable with `--verbose` or log level DEBUG) shows:
- Task analysis details (complexity, category detected)
- Rule matching scores for each routing rule
- Model selection from tier
- Confidence scores and reasoning

## Error Handling

Routing is designed to be fault-tolerant:

- **Analysis Failure**: Falls back to moderate complexity if reasoning engine fails
- **Empty Tier**: Uses fallback model (claude-sonnet-5 by default)
- **Invalid Model Name**: Skips invalid models in tier, tries next
- **Complete Failure**: Returns balanced tier with fallback model
- **Security Validation Failure**: Task rejected, fallback model used

No task is ever left without a model — fallback is always available.

## Performance Impact

Routing analysis adds minimal overhead:

- **Complexity Analysis**: ~100-300ms via reasoning engine
- **Category Detection**: <1ms via keyword matching
- **Rule Matching**: <1ms for default ruleset
- **Total per-task**: ~100-300ms for single delegations

For batch delegation:
- Analysis runs in parallel with task execution
- Overhead is amortized across all tasks in the batch

## Cost Savings

Typical cost savings from routing:

| Task Type | Default Tier | Routed Tier | Savings |
|-----------|--------------|-------------|---------|
| List files | balanced | fast_cheap | 70-75% |
| Simple analysis | balanced | fast_cheap | 60-70% |
| Code generation | capable | balanced | 50-60% |
| Architecture design | capable | capable | 0% (full capability needed) |
| Security audit | capable | capable | 0% (full capability needed) |

**Note**: Cost savings are estimates based on typical pricing. Actual savings depend on:
- Your configured cost multipliers
- Model pricing changes
- Input/output token usage patterns

## Security Considerations

Routing includes several security protections:

1. **Input Validation**
   - Task descriptions checked for length and injection patterns
   - Model names validated against injection attempts
   - Cost parameters validated within reasonable bounds

2. **Constraint Enforcement**
   - Security tasks automatically upgraded to CAPABLE tier minimum
   - Research tasks require CAPABLE tier minimum
   - Code tasks require BALANCED tier minimum
   - Read tasks limited to BALANCED tier maximum

3. **No Downgrade of Security**
   - If routing would under-provision a security task, automatic upgrade occurs
   - Security constraints logged explicitly
   - Fallback model is always safe (balanced tier)

## Troubleshooting

### Task routes to less capable model than expected

**Cause**: Task complexity analyzed as lower than expected

**Solution**: Add specific keywords to task description:
- For RESEARCH: include "research", "investigate", "explore", "comprehensive"
- For REASONING: include "design", "reason", "plan", "strategy"
- For CODE: include "implement", "debug", "optimize"

### Routing disabled in logs but configuration says enabled

**Cause**: `delegation.task_aware_routing.enabled` is false, or parent agent model is specified

**Solution**: 
- Check cli-config.yaml delegation section
- If parent agent has explicit model, that's used instead of routing
- Set parent model to empty string to enable routing

### Security constraint upgraded my task to expensive tier

**Expected behavior**: Security and research tasks automatically upgrade to CAPABLE tier

**Solution**:
- If tier is too expensive, review task categorization
- Remove security-related keywords if not truly a security task
- Explicitly specify model if categorization is wrong

## Advanced Configuration

### Custom Model Tiers

Modify model_tiers in cli-config.yaml:

```yaml
delegation:
  task_aware_routing:
    model_tiers:
      fast_cheap:
        - "claude-haiku-4-5-20251001"
        - "gpt-4o-mini"
      balanced:
        - "claude-sonnet-5"
      capable:
        - "claude-opus-5"
      extended:
        - "o1-pro"
```

### Custom Cost Multipliers

Adjust cost_multipliers to match your actual pricing:

```yaml
delegation:
  task_aware_routing:
    cost_multipliers:
      fast_cheap: 1.0      # Your actual cheap model cost
      balanced: 4.0        # Adjust based on your pricing
      capable: 8.0
      extended: 15.0
```

### Adjust Complexity Thresholds

Fine-tune where tasks cross complexity boundaries:

```yaml
delegation:
  task_aware_routing:
    complexity_thresholds:
      simple_moderate: 0.25   # More tasks → SIMPLE
      moderate_complex: 0.70  # Raise the bar for COMPLEX
      complex_critical: 0.90  # Fewer tasks → CRITICAL
```

### Disable Category Constraints

Remove min/max tier constraints (not recommended):

```yaml
delegation:
  task_aware_routing:
    category_overrides: {}  # Empty dict disables all constraints
```

## API Reference

### `route_task_to_model(task_description, available_tools=0)`

**Returns**: `(model_id: str, decision: RoutingDecision)`

**RoutingDecision fields**:
- `recommended_tier`: ModelTier enum (FAST_CHEAP, BALANCED, CAPABLE, EXTENDED)
- `recommended_model`: str (specific model name, e.g., "claude-opus-5")
- `complexity`: ReasoningComplexity (SIMPLE, MODERATE, COMPLEX, CRITICAL)
- `category`: TaskCategory or None (READ, ANALYZE, CODE, REASONING, RESEARCH, SECURITY)
- `confidence`: float [0.0-1.0] (how confident in the routing decision)
- `reasoning`: str (human-readable explanation)
- `cost_savings_estimate`: float [0-100] (estimated % savings vs default balanced tier)

### `TaskAwareModelRouter.analyze_task(task_description, available_tools=0)`

Lower-level method for advanced analysis:

**Returns**: `RoutingDecision` (same as above)

**Usage**: For tools that need detailed routing analysis

### `RoutingSecurityValidator` static methods

- `validate_task_description(description)`: Check for injection attempts
- `validate_model_name(name)`: Ensure model name is safe
- `validate_cost_multiplier(value)`: Check multiplier in bounds
- `enforce_category_tier_constraints(category, tier)`: Apply safety constraints

## FAQ

**Q: Will routing route security-critical tasks to a cheap model?**

A: No. Security tasks automatically upgrade to CAPABLE tier minimum. This constraint is enforced regardless of complexity analysis.

**Q: Can I disable routing for specific delegations?**

A: Yes, specify an explicit model in the delegation call. This bypasses routing entirely.

**Q: What if routing fails?**

A: A safe fallback is always used (balanced tier, claude-sonnet-5). No task is left without a model.

**Q: Does routing increase latency?**

A: Yes, by ~100-300ms per task due to complexity analysis. This is offset by faster execution on cheaper models for simple tasks.

**Q: Can I customize the routing rules?**

A: Currently, rules are built-in. You can adjust thresholds, tier mappings, and cost multipliers via configuration. Future versions may support custom rules via plugins.

**Q: How often are routing decisions logged?**

A: Every routing decision is logged at INFO level with full details. Disable with appropriate logging configuration if too verbose.

## Future Enhancements

Planned improvements:

1. **User-Defined Routing Rules**: Define custom rules via configuration
2. **Adaptive Routing**: Learn from past routing decisions and outcomes
3. **Budget-Aware Routing**: Route based on per-delegation cost budgets
4. **Per-User Routing Profiles**: Different routing strategies for different users
5. **Metrics and Analytics**: Track routing decisions, savings, and outcomes
6. **Multi-Provider Support**: Route across Azure OpenAI, Anthropic, etc.
