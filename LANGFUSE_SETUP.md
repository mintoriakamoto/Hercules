# Langfuse Observability Integration for Hercules

**Real-time LLM observability for the Hercules agent runtime.** Track conversations, LLM calls, tool execution, errors, and performance.

## Quick Start

### 1. Create Langfuse Account

```bash
# Go to https://langfuse.com/cloud (free tier available)
# or self-host: https://langfuse.com/self-hosting
```

### 2. Get API Credentials

1. Create a new project in Langfuse
2. Go to **Settings → API Keys**
3. Create a new API key pair (or use existing)
4. Copy **Public Key** (`pk-lf-...`) and **Secret Key** (`sk-lf-...`)

### 3. Set Environment Variables

```bash
export LANGFUSE_PUBLIC_KEY="pk-lf-..."
export LANGFUSE_SECRET_KEY="sk-lf-..."
export LANGFUSE_BASE_URL="https://cloud.langfuse.com"  # or your self-hosted URL
```

### 4. Install Langfuse Python SDK

```bash
pip install langfuse
# or if already in Hercules repo:
uv pip install langfuse
```

### 5. Test Integration

```bash
python demo_langfuse.py
```

You should see traces appear in your Langfuse dashboard at:
→ https://cloud.langfuse.com/project/YOUR_PROJECT_ID/traces

---

## Integration Patterns

### Pattern 1: Auto-Instrument Existing Agent

Wrap your agent to automatically trace all conversations:

```python
from langfuse_integration import LangfuseObserver

# Initialize observer
observer = LangfuseObserver()

# Wrap agent
agent = observer.instrument_agent(agent)

# Every call to agent.run_conversation() now traces automatically
response = agent.run_conversation("Your prompt here")

# Flush events at shutdown
observer.flush()
```

### Pattern 2: Manual Tracing with Spans

For fine-grained control over what gets traced:

```python
from langfuse_integration import LangfuseObserver

observer = LangfuseObserver()

# Start a trace
observer.start_trace(name="search-and-summarize", user_id="user_123")

# Log individual operations
with observer.span_context("web-search") as span:
    results = search_web("query")
    span.update(output=results)

# Log LLM call
observer.log_generation(
    model="claude-opus-4",
    prompt="Summarize this...",
    completion="Summary is...",
    input_tokens=100,
    output_tokens=50,
)

# Log tool execution
observer.log_tool_call(
    tool_name="save-results",
    tool_input={"key": "results"},
    tool_output={"id": "doc_123"},
    success=True,
)

# End trace
observer.end_trace()
observer.flush()
```

### Pattern 3: Context Manager Tracing

Cleanest approach for automatic lifecycle management:

```python
observer = LangfuseObserver()

with observer.trace_context("my-task", user_id="user_456") as trace_id:
    # All work here is traced
    
    with observer.span_context("substep") as span:
        result = do_work()
        span.update(output=result)
    
    # Trace auto-ends on context exit
```

---

## What Gets Captured

### 1. **Agent Conversations**
- User prompts and agent responses
- Conversation duration
- Model used
- Status (completed/failed)
- Error messages and types

### 2. **LLM Calls** (Generations)
- Model name and input
- Completion text
- Token usage (input/output)
- Estimated cost in USD
- Call duration

### 3. **Tool Execution**
- Tool name and input arguments
- Tool output/results
- Execution success/failure
- Error details if failed
- Execution time

### 4. **Performance Metrics**
- Total tokens per trace
- Cost per conversation
- Latency per operation
- Retry attempts
- Error rates by type

### 5. **Structured Context**
- User IDs for multi-user tracking
- Custom metadata and tags
- Error classification
- Recovery statistics

---

## Viewing Traces

### In Langfuse Dashboard

1. Navigate to **Traces** tab
2. See all conversations and their sub-operations
3. Click on a trace to see:
   - Full conversation flow
   - Token usage breakdown
   - Cost analysis
   - Error details
   - Custom metadata

### Via Langfuse CLI

```bash
# Install CLI
pip install langfuse-cli

# View latest traces
npx langfuse-cli api observations list --limit 10

# Get specific trace
npx langfuse-cli api observations get --id TRACE_ID
```

### Programmatically

```python
from langfuse import Langfuse

langfuse = Langfuse(
    public_key="pk-lf-...",
    secret_key="sk-lf-...",
)

# Query traces
traces = langfuse.get_trace_list(limit=10)
for trace in traces:
    print(f"{trace.id}: {trace.name} ({trace.timestamp})")
```

---

## Integration with Hercules Agent

### Option A: Instrument at Agent Creation

```python
# In your agent initialization code (e.g., hercules_cli/main.py)
from langfuse_integration import LangfuseObserver

# Create agent
agent = AIAgent(...)

# Conditionally instrument for observability
if os.getenv("LANGFUSE_ENABLED") == "true":
    observer = LangfuseObserver()
    agent = observer.instrument_agent(agent)
    # Store observer for later flush
    app_state.langfuse_observer = observer
```

### Option B: Wrap Specific Functions

```python
# In run_agent.py or agent/conversation_loop.py
from langfuse_integration import LangfuseObserver

observer = get_observer()

@wraps(handle_function_call)
def handle_function_call_traced(tool_call_id, function_name, arguments):
    start_time = time.time()
    try:
        result = handle_function_call(tool_call_id, function_name, arguments)
        observer.log_tool_call(
            tool_name=function_name,
            tool_input=arguments,
            tool_output=result,
            success=True,
            duration_ms=(time.time() - start_time) * 1000,
        )
        return result
    except Exception as e:
        observer.log_tool_call(
            tool_name=function_name,
            tool_input=arguments,
            tool_output=None,
            success=False,
            error=str(e),
            duration_ms=(time.time() - start_time) * 1000,
        )
        raise
```

### Option C: Gateway-Level Integration

Add tracing to the gateway daemon for all sessions:

```python
# In gateway/run.py or platform adapter
from langfuse_integration import get_observer

class GatewayRunner:
    def __init__(self):
        self.observer = get_observer(enable=True)
    
    async def handle_message(self, session, message):
        # Every message flows through tracing
        if self.observer:
            self.observer.start_trace(
                name="gateway-message",
                user_id=session.user_id,
                metadata={"platform": session.platform}
            )
        try:
            result = await self.process_message(session, message)
            self.observer.end_trace(metadata={"status": "success"})
            return result
        except Exception as e:
            self.observer.end_trace(metadata={"status": "error", "error": str(e)})
            raise
```

---

## Configuration

### Environment Variables

```bash
# Required
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...

# Optional
LANGFUSE_BASE_URL=https://cloud.langfuse.com  # default
LANGFUSE_ENABLED=true  # enable/disable via env
```

### Constructor Options

```python
observer = LangfuseObserver(
    public_key="pk-lf-...",              # API public key
    secret_key="sk-lf-...",              # API secret key
    base_url="https://cloud.langfuse.com",  # Langfuse instance URL
    enable_async=False,                  # Async flush (non-blocking)
)
```

---

## Performance Impact

- **Minimal overhead**: Traces are queued and flushed asynchronously
- **Configurable batch size**: Default 100 events per batch, tunable
- **Non-blocking**: By default, trace logging doesn't block agent operations
- **Optional enablement**: Can be fully disabled via env var or conditional import

---

## Troubleshooting

### "Langfuse not installed"

```bash
pip install langfuse
```

### "Credentials not provided"

Ensure environment variables are set:

```bash
export LANGFUSE_PUBLIC_KEY="pk-lf-..."
export LANGFUSE_SECRET_KEY="sk-lf-..."
export LANGFUSE_BASE_URL="https://cloud.langfuse.com"
```

### "Connection refused"

- Check `LANGFUSE_BASE_URL` is correct
- Verify network access to Langfuse (firewall/VPN)
- For self-hosted: ensure deployment is running

### "Traces not appearing"

1. Call `observer.flush()` before shutdown
2. Check Langfuse dashboard filters (project selection, date range)
3. Verify API keys have write permissions
4. Check logs for errors with `logging.getLogger("langfuse_integration").setLevel(logging.DEBUG)`

---

## Examples

### Track User Interactions

```python
observer.start_trace(
    name="user-request",
    user_id="user_12345",
    metadata={"source": "web", "session_id": "sess_456"}
)
```

### Monitor Performance

```python
observer.log_generation(
    model="claude-opus-4",
    prompt="...",
    completion="...",
    input_tokens=1200,
    output_tokens=450,
    cost_usd=0.0075,  # Actual cost from API response
)
```

### Track Failures

```python
observer.end_trace(metadata={
    "status": "failed",
    "error": "API rate limit exceeded",
    "error_type": "RateLimitError",
    "retry_count": 3,
})
```

---

## References

- **Langfuse Docs**: https://langfuse.com/docs
- **Python SDK Guide**: https://langfuse.com/docs/sdk/python/guide
- **Self-Hosting**: https://langfuse.com/self-hosting
- **Pricing**: https://langfuse.com/pricing

---

## Support

For issues with this integration:
- Check logs: `logging.getLogger("langfuse_integration").setLevel(logging.DEBUG)`
- Test with `python demo_langfuse.py`
- Review Langfuse docs: https://langfuse.com/docs

For issues with Langfuse itself:
- Langfuse GitHub: https://github.com/langfuse/langfuse
- Langfuse Discord: https://discord.gg/WGMPFb57yc
