# OpenCode Authentication Guide

This guide addresses authentication setup and error handling for OpenCode Zen and OpenCode Go providers.

## Overview

Hercules supports two OpenCode providers:

| Provider | ID | Base URL | Purpose |
|----------|----|-----------|-|
| **OpenCode Zen** | `opencode-zen` | `https://opencode.ai/zen/v1` | General API gateway |
| **OpenCode Go** | `opencode-go` | `https://opencode.ai/zen/go/v1` | Multi-model API gateway (GLM, Kimi, MiniMax, Qwen) |

## Quick Setup

### OpenCode Zen

```bash
# Get API key from https://opencode.ai/zen
export OPENCODE_ZEN_API_KEY="your-api-key-here"

# Verify it works
hercules model list | grep opencode-zen

# Or switch to it
hercules switch opencode-zen
```

### OpenCode Go

```bash
# Get API key from https://opencode.ai/go  
export OPENCODE_GO_API_KEY="your-api-key-here"

# List available models
hercules model list | grep opencode-go

# Switch to it
hercules switch go          # or "opencode-go"
```

## Configuration Details

### Environment Variables

**OpenCode Zen:**
- `OPENCODE_ZEN_API_KEY` — API key (required)
- `OPENCODE_ZEN_BASE_URL` — Custom base URL (optional, defaults to https://opencode.ai/zen/v1)

**OpenCode Go:**
- `OPENCODE_GO_API_KEY` — API key (required)
- `OPENCODE_GO_BASE_URL` — Custom base URL (optional, defaults to https://opencode.ai/zen/go/v1)

### Persistent Configuration

Save credentials in `~/.hercules/config.yaml`:

```yaml
providers:
  opencode-zen:
    api_key: ${OPENCODE_ZEN_API_KEY}
    base_url: https://opencode.ai/zen/v1
    
  opencode-go:
    api_key: ${OPENCODE_GO_API_KEY}
    base_url: https://opencode.ai/zen/go/v1
```

Environment variables take precedence over config file values.

## Common Authentication Errors

### Error 1: "Unauthorized" or 401

**Symptoms:**
```
provider authentication failed: 401 Unauthorized
incorrect api key
```

**Causes:**
1. API key is missing or blank
2. API key is incorrect/expired
3. API key doesn't have sufficient permissions

**Fix:**
```bash
# 1. Verify key is set
echo $OPENCODE_ZEN_API_KEY

# 2. Check it's not empty
test -n "$OPENCODE_ZEN_API_KEY" && echo "Key is set" || echo "Key is empty"

# 3. Get a fresh key from https://opencode.ai/
export OPENCODE_ZEN_API_KEY="sk-..."

# 4. Test authentication
hercules model list | grep opencode-zen
```

### Error 2: "Provider not available"

**Symptoms:**
```
opencode-zen does not appear in provider list
opencode-zen is not available
```

**Causes:**
1. API key is not set
2. Provider is not configured
3. Credentials not found in config or environment

**Fix:**
```bash
# Set API key first
export OPENCODE_ZEN_API_KEY="your-key"

# Verify it appears
hercules model list | grep opencode-zen

# Check doctor for issues
hercules doctor
```

### Error 3: "Extra inputs are not permitted"

**Symptoms:**
```
opencode-go rejected: Extra inputs are not permitted, field: 'messages[N]._empty_recovery_synthetic'
```

**Causes:**
This is a known issue with strict OpenCode Go validation. The gateway rejects certain internal message fields that permissive providers silently ignore.

**Fix:**
```bash
# Update to latest Hercules version (fix is in place)
hercules update

# Or work around by using message sanitization
# (Automatically handled in chat completions layer)
```

### Error 4: "Token limit exceeded"

**Symptoms:**
```
context_length_exceeded: 131072 tokens max
max_tokens exceeded for model
```

**Causes:**
- Message is too long for the model's context window
- Model has smaller limit than expected
- Context includes too much history

**Fix:**
```bash
# Check model's max token limit
hercules model info mimo-v2.5-pro
# Shows max_tokens (e.g., 131072 for Mimo)

# Reduce context size
# 1. Start fresh conversation
# 2. Use /clear to reset memory
# 3. Or switch to model with larger context
```

### Error 5: "Model not found"

**Symptoms:**
```
opencode-go: model 'glm-5.1' not found
The model does not exist on this provider
```

**Causes:**
1. Model name is incorrect
2. Model is not available in your region
3. Provider has updated model list

**Fix:**
```bash
# List available models
hercules model list | grep opencode-go

# Or get all models
hercules model info --all | grep opencode

# Update your model list (refresh from API)
hercules model refresh
```

## Model Availability

### OpenCode Zen

**Base models available depend on API tier.** Check:
- https://opencode.ai/zen/models
- `hercules model list`

Common models:
- Claude (Anthropic)
- GPT-4 (OpenAI)
- Grok (xAI)
- Local models via OpenCode

### OpenCode Go

**Multi-model gateway with three API surfaces:**

| Model Family | API Type | Location |
|--------------|----------|----------|
| GLM / Kimi | OpenAI-compatible | `/v1/chat/completions` |
| MiniMax | Anthropic Messages | `/v1/messages` |
| Qwen 3.7+ | Anthropic Messages | `/v1/messages` |

**Available models:**
```
glm-5.1          GLM model (OpenAI API)
glm-5            GLM 5 (OpenAI API)
kimi-k2.6        Kimi K2.6 (OpenAI API)
kimi-k2.5        Kimi K2.5 (OpenAI API)
mimo-v2-pro      Mimo V2 Pro (Anthropic API)
mimo-v2-omni     Mimo V2 Omni (Anthropic API)
minimax-m2.7     MiniMax M2.7 (Anthropic API)
minimax-m2.5     MiniMax M2.5 (Anthropic API)
```

## API Mode Selection

OpenCode Go uses two API modes transparently:

**Automatic selection by model:**
```python
# Hercules selects based on model name
if model in {"glm", "kimi"}:
    api_mode = "openai"  # Use /v1/chat/completions
elif model in {"mimo", "minimax"}:
    api_mode = "anthropic"  # Use /v1/messages
```

**What this means:**
- Different models have different API surfaces
- Hercules automatically adapts request format
- You don't need to worry about API differences
- Message schema is normalized transparently

## Credential Rotation

### Updating API Key

```bash
# 1. Get new key from OpenCode dashboard
# 2. Update environment
export OPENCODE_GO_API_KEY="sk-new-key..."

# 3. Verify new key works
hercules model list | grep opencode-go

# 4. Update config file if using persistent config
# Edit ~/.hercules/config.yaml with new key

# 5. Clear any cached credentials
rm ~/.hercules/.credentials.cache 2>/dev/null || true

# 6. Test with fresh request
hercules prompt "Hello, test"
```

### Key Expiration

OpenCode keys typically don't expire, but:
- Keys can be revoked by user
- Keys can be rotated via dashboard
- API access can be suspended

**If revoked:**
```bash
# Error will be: "token_invalidated" or "token_revoked"
# Get a new key and export it
export OPENCODE_GO_API_KEY="sk-..."
```

## Rate Limiting

OpenCode applies rate limits per API tier:

**Rate limit errors:**
```
429 Too Many Requests
rate_limit: Quota exceeded
```

**Handling:**
- Hercules automatically retries with exponential backoff
- Default retry behavior: 3 retries with 2s→4s→8s delays
- Check your API tier for actual limits

**To reduce rate limiting:**
1. Upgrade API tier
2. Request longer time windows
3. Batch requests instead of streaming

## Troubleshooting

### Step 1: Verify API Key

```bash
# Check it's set
echo "Key: $OPENCODE_ZEN_API_KEY"

# Check it's not empty
test -n "$OPENCODE_ZEN_API_KEY" && echo "✓ Key is set" || echo "✗ Key is empty"

# Check format (usually starts with 'sk-')
echo "$OPENCODE_ZEN_API_KEY" | grep -E '^[a-zA-Z0-9_-]+$' && echo "✓ Format looks valid"
```

### Step 2: Test Connectivity

```bash
# Test direct API call
curl -H "Authorization: Bearer $OPENCODE_ZEN_API_KEY" \
     https://opencode.ai/zen/v1/models

# Should return JSON list of models, not 401 error
```

### Step 3: Check Hercules Configuration

```bash
# Run doctor diagnostics
hercules doctor

# Check available providers
hercules model list

# Check provider-specific status
hercules model list | grep opencode
```

### Step 4: Enable Debug Logging

```bash
# Run with debug output
HERCULES_DEBUG=1 hercules switch opencode-zen

# Or verbose mode
hercules --verbose model list
```

## See Also

- **Provider Registry:** `hercules_cli/auth.py` — Provider configurations
- **Chat Completions:** `agent/transports/chat_completions.py` — API mode selection
- **Model Metadata:** `agent/model_metadata.py` — Model definitions
- **Error Handling:** `agent/error_classifier.py` — Error classification

## Support

- **OpenCode Zen:** https://opencode.ai/zen
- **OpenCode Go:** https://opencode.ai/go
- **Hercules Issues:** https://github.com/mintoriakamoto/Hercules/issues
