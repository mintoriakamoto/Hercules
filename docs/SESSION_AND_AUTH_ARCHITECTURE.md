# Session and Authentication Architecture

This document explains how Hercules manages sessions, authentication, and provider credentials across concurrent requests and multiple integration points.

## Overview

Hercules uses three complementary systems:

1. **ContextVar-based Session Context** — Task-local session metadata
2. **Provider Authentication Layer** — Credential resolution and caching
3. **Gateway Request Headers** — Request-scoped identity propagation

## Part 1: Session Context (gateway/session_context.py)

### Problem Solved

The gateway processes messages concurrently via `asyncio`. The old code used `os.environ` (process-global):

```python
# BAD: Race condition
os.environ["HERCULES_SESSION_THREAD_ID"] = str(context.source.thread_id)
# Message A's thread ID gets overwritten by Message B if they arrive simultaneously
```

### Solution: ContextVar

Each `asyncio` task gets its own task-local copy:

```python
from contextvars import ContextVar
_SESSION_THREAD_ID = ContextVar("HERCULES_SESSION_THREAD_ID", default=_UNSET)

# GOOD: Concurrent messages have isolated thread IDs
_SESSION_THREAD_ID.set(str(context.source.thread_id))
```

### Session Variables

All session context variables defined in `gateway/session_context.py`:

| Variable | Purpose | Example |
|----------|---------|---------|
| `HERCULES_SESSION_PLATFORM` | Message source (Telegram, Discord, etc) | "telegram" |
| `HERCULES_SESSION_CHAT_ID` | Conversation ID | "123456789" |
| `HERCULES_SESSION_THREAD_ID` | Thread/topic in chat | "thread_42" |
| `HERCULES_SESSION_USER_ID` | User identifier | "user_abc" |
| `HERCULES_SESSION_KEY` | Session routing key | "xsession:...:v1" |
| `HERCULES_SESSION_ID` | Durable session database ID | "session_uuid" |
| `HERCULES_UI_SESSION_ID` | Desktop/TUI window ID | "ui_session_123" |
| `HERCULES_SESSION_PROFILE` | User profile name | "default" |

### How to Use Session Context

**Reading values:**
```python
from gateway.session_context import get_session_env

platform = get_session_env("HERCULES_SESSION_PLATFORM", "")
chat_id = get_session_env("HERCULES_SESSION_CHAT_ID", "")
```

**Setting values (gateway use only):**
```python
from gateway.session_context import set_session_vars

set_session_vars({
    "HERCULES_SESSION_PLATFORM": "telegram",
    "HERCULES_SESSION_CHAT_ID": str(context.chat_id),
})
```

**Key invariant:** Session context is **task-local**, so concurrent requests never interfere.

## Part 2: Provider Authentication Layer

### Architecture

Provider auth flows through multiple layers:

```
User Input → Gateway Adapter → AIAgent → Chat Provider
    ↓             ↓               ↓           ↓
Platform      Extracts       Resolve      Use
Identity    Credentials       Auth       Token
```

### Configuration

Provider credentials are defined in `hercules_cli/config.py`:

```yaml
providers:
  openai:
    api_key: ${OPENAI_API_KEY}  # Read from environment
    base_url: https://api.openai.com/v1
  anthropic:
    api_key: ${ANTHROPIC_API_KEY}
    base_url: https://api.anthropic.com
```

### Resolution Flow

1. **Check environment** → `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc
2. **Check config file** → `.hercules/config.yaml` (user profile)
3. **Fallback chain** — See `hercules_cli/fallback_config.py`
4. **Error handling** — Graceful degradation if credentials missing

### Tools Requiring Approval

Certain tools need explicit user approval before execution:

**Types of approval:**
- **Execution approval** — "Allow running this tool?"
- **Output display** — "Show this sensitive output?"
- **File operations** — "Read/write this file?"
- **Network operations** — "Make this HTTP request?"

**Approval flow:**
```python
from tools.approval import request_approval

verdict = request_approval(
    kind="execution",
    tool="execute_code",
    description="Run Python code in workspace"
)
if verdict.approved:
    execute_code()
```

## Part 3: Gateway Request Headers (xsession)

### The xsession Header

The `xsession` header is a composite identity token:

```
xsession: xsession:platform=telegram:chat_id=123:thread_id=456:user_id=abc:v1
```

**Components:**
- `platform` — Message source
- `chat_id` — Conversation ID
- `thread_id` — Thread/topic in conversation
- `user_id` — User identifier
- `v1` — Protocol version

### Where xsession is Used

1. **Gateway → Agent Communication** — Propagate session context
2. **Agent → Tool IPC** — Pass session identity to subprocesses
3. **Background Tasks** — Route async completions back to correct session
4. **Desktop/TUI Routing** — Identify which window completed the request

### Session Key Format

`HERCULES_SESSION_KEY` is a structured identifier used for session routing:

```
xsession:platform=telegram:chat_id=123:user_id=abc:v1
```

**Used by:**
- Approval system — Route user responses to correct session
- Completion queue — Wake correct listener for async results
- Memory store — Scope session history by identity
- Tool execution — Know where to return outputs

## Part 4: Bringing It Together

### Typical Request Flow

```
1. User sends message on Telegram
2. Gateway adapter receives message
3. set_session_vars() establishes context:
   - HERCULES_SESSION_PLATFORM = "telegram"
   - HERCULES_SESSION_CHAT_ID = message.chat.id
   - HERCULES_SESSION_USER_ID = message.from_user.id
4. Create xsession header from context variables
5. AIAgent receives request with xsession header
6. Tools access session context via get_session_env()
7. Background completions use xsession to route back to sender
8. Approval system uses xsession to identify approver
```

### Example: Command Execution Tool

```python
from gateway.session_context import get_session_env
from tools.approval import request_approval

def execute_terminal_command(cmd: str):
    # Get session identity
    platform = get_session_env("HERCULES_SESSION_PLATFORM")
    chat_id = get_session_env("HERCULES_SESSION_CHAT_ID")
    
    # Request approval (routed via xsession header)
    verdict = request_approval(
        kind="execution",
        tool="terminal",
        description=f"Run: {cmd}"
    )
    
    if verdict.approved:
        result = run_command(cmd)
        # Background task uses xsession to send result back
        notify_completion(platform, chat_id, result)
```

## Part 5: Provider-Specific Login Flows

### OpenRouter / OpenAI Compatible

```python
from agent.transports.openrouter import OpenRouterTransport

provider = OpenRouterTransport(
    api_key=get_session_env("OPENROUTER_API_KEY"),
    model="meta-llama/llama-2-70b-chat"
)
response = provider.complete(messages, tools=tools)
```

### Anthropic (Claude)

```python
from agent.transports.anthropic import AnthropicTransport

provider = AnthropicTransport(
    api_key=get_session_env("ANTHROPIC_API_KEY"),
    model="claude-3-opus-20240229"
)
response = provider.complete(messages, tools=tools)
```

### Grok (xAI)

```python
from agent.transports.xai import XAITransport

provider = XAITransport(
    api_key=get_session_env("XAI_API_KEY"),
    model="grok-beta"
)
response = provider.complete(messages, tools=tools)
```

## Part 6: Multi-Session Gateway Patterns

### Desktop App (Multiple Windows)

Each desktop window has its own `HERCULES_UI_SESSION_ID`:

```
Window 1: HERCULES_UI_SESSION_ID = "ui_session_abc123"
Window 2: HERCULES_UI_SESSION_ID = "ui_session_def456"
→ Background completions route to correct window
```

### Telegram (Topics/Threads)

Session context includes both chat and thread:

```
HERCULES_SESSION_CHAT_ID = "123456789"
HERCULES_SESSION_THREAD_ID = "42"
→ Completions route to correct topic
```

### API Server (Stateless)

```python
# API requests don't support async delivery
_SESSION_ASYNC_DELIVERY.set(False)
```

## Part 7: Security Considerations

### Session Isolation

- ✅ ContextVars are task-local (concurrent isolation)
- ✅ Sessions never leak between concurrent requests
- ✅ Subprocess environment is explicitly configured
- ⚠️ **Caveat:** Single-threaded CLI doesn't use ContextVars (not needed)

### Credential Handling

- ✅ Environment variables (encrypted at rest in CI)
- ✅ Config files (user-readable, never committed)
- ✅ Approval system (explicit user consent)
- ⚠️ **Never log credentials** — All logging strips keys

### Approval System

- ✅ Tools requiring approval throw if unapproved
- ✅ Approval routed via xsession (identity verified)
- ✅ Timeouts prevent hanging on unapproved operations
- ✅ Fallback: if no interactive user, auto-approve (headless servers)

## Part 8: Testing Session Context

### Unit Tests

```python
from gateway.session_context import set_session_vars, get_session_env

def test_session_isolation():
    # Session 1
    set_session_vars({"HERCULES_SESSION_CHAT_ID": "123"})
    assert get_session_env("HERCULES_SESSION_CHAT_ID") == "123"
    
    # Session 2 (different value, different context)
    set_session_vars({"HERCULES_SESSION_CHAT_ID": "456"})
    assert get_session_env("HERCULES_SESSION_CHAT_ID") == "456"
```

### Integration Tests

```python
async def test_concurrent_requests():
    """Verify concurrent requests have isolated session context."""
    results = await asyncio.gather(
        handle_request(chat_id="123"),  # Sets CHAT_ID=123
        handle_request(chat_id="456"),  # Sets CHAT_ID=456
    )
    # Each request sees only its own chat_id, not the other's
```

## References

- **Gateway entry:** `gateway/run.py` — Message routing
- **Session context:** `gateway/session_context.py` — ContextVar definitions
- **Approval system:** `tools/approval.py` — User consent
- **Provider auth:** `agent/transports/` — LLM provider integration
- **Config:** `hercules_cli/config.py` — Credential sources
- **Examples:** `tests/gateway/` — Real usage patterns
