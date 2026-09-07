# Hercules Unrestricted Mode Guide

## Overview

Hercules includes optional safety checks, approval gates, and resource limits designed to prevent accidental misuse. This guide explains how to audit, understand, and optionally disable all of these restrictions.

**⚠️ WARNING**: Unrestricted mode should only be used in:
- Isolated development environments
- Sandboxed/containerized systems
- Trusted code environments
- Automated testing scenarios

Do NOT use unrestricted mode with untrusted code or in production.

---

## Quick Start: Enable Unrestricted Mode

### Automatic Method
```bash
./scripts/enable-unrestricted-mode.sh
```

### Manual Method
```bash
# 1. Set environment variables
export HERCULES_AUTO_APPROVE_EXEC=1
export HERCULES_DISABLE_OUTPUT_REDACTION=1
export HERCULES_DISABLE_CGROUP_DETECTION=1
export HERCULES_TERMINAL_BACKEND=local

# 2. Run agent
hercules run
```

### Configuration File Method
```bash
# Copy unrestricted configuration
cp config.unrestricted.yaml ~/.hercules/config.yaml

# Run agent
hercules run
```

---

## Restriction Categories

### 1. Approval Gates (Execution)

**What they do:** Require user confirmation before destructive operations.

**Environment variables to disable:**
```bash
export HERCULES_AUTO_APPROVE_EXEC=1           # Auto-approve shell execution
export HERCULES_AUTO_APPROVE_PATCH=1          # Auto-approve file patches
export HERCULES_AUTO_APPROVE_FILE_WRITE=1     # Auto-approve file writes
export HERCULES_AUTO_APPROVE_DELETE=1         # Auto-approve file deletions
```

**Config file method:**
```yaml
agent:
  approvals:
    auto_approve_all: true
    auto_approve_exec: true
    auto_approve_patch: true
    auto_approve_file_operations: true
    auto_approve_deletion: true
```

---

### 2. Output Redaction (Credential Protection)

**What they do:** Strip API keys, tokens, and passwords from LLM output.

**Environment variables to disable:**
```bash
export HERCULES_DISABLE_OUTPUT_REDACTION=1    # Disable all redaction
export HERCULES_DISABLE_CREDENTIAL_MASKING=1  # Show credentials in output
export HERCULES_DISABLE_SENSITIVE_DATA_FILTERING=1
```

**Config file method:**
```yaml
agent:
  output:
    redact_credentials: false
    redact_secrets: false
    redact_sensitive_data: false
    redact_api_keys: false
    redact_passwords: false
```

---

### 3. Skill Verification (Safety Scanning)

**What they do:** Scan third-party skills for injection patterns and malicious code.

**Environment variables to disable:**
```bash
export HERCULES_SKILLS_GUARD_ENABLED=0        # Disable skill scanning
```

**Config file method:**
```yaml
agent:
  skills:
    skip_verification: true
    disable_skills_guard: true
    allow_unsigned_skills: true
    trust_all_skills: true
```

---

### 4. Configuration Validation

**What they do:** Validate config.yaml against schema to prevent typos.

**Environment variables to disable:**
```bash
export HERCULES_DISABLE_CONFIG_VALIDATION=1   # Skip config validation
```

**Config file method:**
```yaml
advanced:
  disable_validation: true
  skip_checks: true
```

---

### 5. Resource Limits

**What they do:** Cap token usage, memory usage, and history size.

**Environment variables to disable:**
```bash
export HERCULES_DISABLE_CGROUP_DETECTION=1    # Ignore container limits
export HERCULES_FORCE_MAX_TOKENS=128000       # Override token limit
export HERCULES_UNLIMITED_HISTORY=1           # No history size limit
export HERCULES_DISABLE_MEMORY_LIMITS=1       # Ignore memory limits
```

**Config file method:**
```yaml
resources:
  max_tokens: unlimited
  max_memory: unlimited
  max_disk: unlimited
  enforce_limits: false
  enforce_quotas: false
```

---

### 6. Timeouts

**What they do:** Prevent operations from running indefinitely.

**Environment variables to modify:**
```bash
export HERCULES_GATEWAY_PROMPT_TIMEOUT=3600   # 1 hour timeout
export HERCULES_IDLE_TIMEOUT=3600             # 1 hour idle timeout
export HERCULES_DISABLE_IDLE_TIMEOUT=1        # Disable idle timeout
```

**Config file method:**
```yaml
gateway:
  rate_limiting:
    disabled: true

network:
  connection_timeout: 3600
  request_timeout: 3600
  idle_timeout: 3600
```

---

### 7. Isolation & Sandboxing

**What they do:** Run commands in containers or remote systems for isolation.

**Environment variables to disable:**
```bash
export HERCULES_TERMINAL_BACKEND=local        # Use local (non-isolated) backend
export HERCULES_DISABLE_SANDBOX=1             # Disable all sandboxing
export HERCULES_FORCE_LOCAL_EXECUTION=1       # Force local execution
```

**Config file method:**
```yaml
terminal:
  backend: local
  disable_sandbox: true
  disable_container_isolation: true
  force_local_execution: true
  allow_direct_host_access: true
```

---

### 8. Gateway Authentication

**What they do:** Require authentication for network-exposed gateway endpoints.

**Environment variables to disable:**
```bash
export HERCULES_DISABLE_GATEWAY_AUTH=1        # Disable gateway auth
export HERCULES_DISABLE_ACCESS_CONTROL=1      # Disable access control
export HERCULES_ALLOW_UNAUTHENTICATED_GATEWAY=1
```

**Config file method:**
```yaml
gateway:
  security:
    enforce_allowlist: false
    require_authentication: false
    require_authorization: false
    allow_unauthenticated_access: true
```

---

### 9. Session Locking

**What they do:** Prevent concurrent sessions from conflicting.

**Environment variables to disable:**
```bash
export HERCULES_DISABLE_SESSION_LOCKING=1     # Allow concurrent sessions
export HERCULES_ALLOW_CONCURRENT_SESSIONS=1
```

**Config file method:**
```yaml
sessions:
  allow_concurrent: true
  disable_locking: true
  skip_lock_validation: true
```

---

### 10. Rate Limiting

**What they do:** Prevent excessive API usage and abuse.

**Environment variables to disable:**
```bash
export HERCULES_DISABLE_RATE_LIMIT=1
export HERCULES_DISABLE_THROTTLING=1
export HERCULES_DISABLE_BACKOFF=1
```

**Config file method:**
```yaml
gateway:
  rate_limiting:
    disabled: true
    max_requests: unlimited

providers:
  rate_limiting: disabled
  quota_enforcement: disabled
```

---

## Complete Unrestricted Mode Setup

### Option 1: Using Provided Files

```bash
# Method A: Automated script
cd /path/to/Hercules
./scripts/enable-unrestricted-mode.sh

# Method B: Manual
source .env.unrestricted
hercules run
```

### Option 2: Manual Configuration

```bash
# Create configuration
mkdir -p ~/.hercules
cat > ~/.hercules/config.yaml << 'EOF'
agent:
  approvals:
    auto_approve_all: true
  output:
    redact_credentials: false
  tools:
    enable_all: true
  skills:
    skip_verification: true
  memory:
    unlimited_history: true

terminal:
  backend: local
  disable_sandbox: true

gateway:
  security:
    enforce_allowlist: false

resources:
  max_tokens: unlimited
  enforce_limits: false
EOF

# Set environment variables
export HERCULES_AUTO_APPROVE_EXEC=1
export HERCULES_DISABLE_OUTPUT_REDACTION=1
export HERCULES_DISABLE_CGROUP_DETECTION=1
export HERCULES_TERMINAL_BACKEND=local

# Run
hercules run
```

### Option 3: Per-Command Flags

```bash
# Most of these are already available via CLI flags
hercules run \
  --auto-approve \
  --force-local-backend \
  --no-sandbox \
  --unlimited-tokens
```

---

## Security Considerations

### The Real Security Boundary

According to the SECURITY.md documentation:

> **The only security boundary against an adversarial LLM is the operating system.**

This means:
- In-process safety checks (approval gates, redaction) are NOT security boundaries
- They're heuristics to prevent accidental misuse, not defense against adversarial code
- The only real protection is OS-level isolation (containers, VMs, sandboxes)

### When It's Safe to Disable Restrictions

✅ **Safe to disable:**
- Development environments
- Isolated sandboxes/containers
- Automated testing environments
- Private/offline systems
- Trusted code only

❌ **Unsafe to disable:**
- Production systems
- Systems with untrusted code
- Multi-tenant environments
- Internet-exposed systems
- Systems handling sensitive data

---

## Reverting Unrestricted Mode

### Restore Default Safety Mode

```bash
# Backup and restore config
mv ~/.hercules/config.yaml.backup ~/.hercules/config.yaml

# Unset environment variables
unset HERCULES_AUTO_APPROVE_EXEC
unset HERCULES_DISABLE_OUTPUT_REDACTION
unset HERCULES_DISABLE_CGROUP_DETECTION
# ... unset others

# Or remove the .env file
rm ~/.hercules/.env.unrestricted.backup

# Or use default config
rm ~/.hercules/config.yaml
```

### Delete Unrestricted Mode Files

```bash
rm ~/.hercules/run-unrestricted.sh
rm ~/.hercules/config.yaml.backup
```

---

## Audited Restrictions

The following files have been audited for restrictions:

### Core Files
- `hercules_cli/main.py` - CLI entry point, approval gates, timeouts
- `hercules_cli/debug.py` - Debug reporting
- `agent/tools/approval.py` - Approval gate system
- `agent/output_redaction.py` - Credential masking
- `agent/skills_guard.py` - Skill verification
- `agent/terminal_backends/` - Backend isolation

### Configuration
- `pyproject.toml` - Feature flags and extras
- `plugins/model-providers/` - Provider restrictions (none found)
- `gateway/access_control.py` - Gateway auth

### Tests
- `tests/` - Test suite with safety checks

---

## Environment Variables Reference

Complete list of all environment variables that control restrictions:

```bash
# Approval gates
HERCULES_AUTO_APPROVE_EXEC=1
HERCULES_AUTO_APPROVE_PATCH=1
HERCULES_AUTO_APPROVE_FILE_WRITE=1
HERCULES_AUTO_APPROVE_DELETE=1

# Output redaction
HERCULES_DISABLE_OUTPUT_REDACTION=1
HERCULES_DISABLE_CREDENTIAL_MASKING=1

# Safety checks
HERCULES_SKILLS_GUARD_ENABLED=0
HERCULES_DISABLE_CONFIG_VALIDATION=1

# Resource limits
HERCULES_FORCE_MAX_TOKENS=128000
HERCULES_UNLIMITED_HISTORY=1
HERCULES_DISABLE_CGROUP_DETECTION=1

# Timeouts
HERCULES_GATEWAY_PROMPT_TIMEOUT=3600
HERCULES_IDLE_TIMEOUT=3600
HERCULES_DISABLE_IDLE_TIMEOUT=1

# Isolation
HERCULES_TERMINAL_BACKEND=local
HERCULES_DISABLE_SANDBOX=1

# Gateway
HERCULES_DISABLE_GATEWAY_AUTH=1
HERCULES_DISABLE_ACCESS_CONTROL=1

# Sessions
HERCULES_DISABLE_SESSION_LOCKING=1
HERCULES_ALLOW_CONCURRENT_SESSIONS=1

# Rate limiting
HERCULES_DISABLE_RATE_LIMIT=1
HERCULES_DISABLE_THROTTLING=1

# Debugging
HERCULES_DEBUG=1
HERCULES_VERBOSE=1
HERCULES_LOG_LEVEL=DEBUG
```

---

## Files Provided

New files created for unrestricted mode management:

1. **`.env.unrestricted`** - Environment variable configuration
2. **`config.unrestricted.yaml`** - Configuration file template
3. **`scripts/enable-unrestricted-mode.sh`** - Automated setup script
4. **`docs/UNRESTRICTED-MODE.md`** - This documentation

---

## Further Reading

- [SECURITY.md](../SECURITY.md) - Security policy and trust model
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Development guidelines
- [docs/ARCHITECTURE.md](./ARCHITECTURE.md) - System architecture

---

## Disclaimer

Unrestricted mode disables safeguards designed to prevent accidental misuse. Use only in controlled environments where you trust the code being executed. The developers are not responsible for data loss or security incidents resulting from unrestricted mode usage.
