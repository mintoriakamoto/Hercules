# Production-Ready Hardening Guide for Hercules Agent

This document describes the production hardening improvements made to the Hercules Agent codebase to ensure enterprise-grade reliability, security, and observability.

## Overview

The Hercules Agent operates as a sophisticated pentesting and automation tool that executes in diverse environments. This guide covers systematic improvements to make it production-ready for deployment in security-critical scenarios.

## Key Improvements

### 1. **Enhanced Error Handling & Observability**

**Problem**: Broad `except Exception` blocks silently swallow errors, making debugging and security auditing difficult.

**Solution**: Implement specific exception handling with contextual logging.

**Files Modified**:
- `agent/context_compressor.py` - Compression failure cooldown lookup
- `gateway/run.py` - Image generation tool output parsing
- `tools/tool_backend_helpers.py` - Configuration loading
- `hercules_cli/auth.py` - Credential file locking

**Best Practice**:
```python
# ❌ AVOID
try:
    result = risky_operation()
except Exception:
    pass  # Silent failure

# ✅ PREFER
try:
    result = risky_operation()
except SpecificExpectedError as e:
    logger.debug("expected error in operation: %s", e)
except (TypeError, ValueError) as e:
    logger.warning("data validation issue: %s", e)
except Exception as e:
    logger.exception("unexpected error: %s", e)
```

### 2. **Input Validation Framework**

**Problem**: User inputs are not uniformly validated, creating injection attack vectors.

**Solution**: Centralized input validation module (`agent/input_validation.py`) with:
- String validation (length, pattern, character whitelist)
- Path traversal prevention
- Command injection detection
- URL validation with scheme whitelisting
- Type-safe integer and array validation

**Usage**:
```python
from agent.input_validation import (
    validate_string,
    validate_path,
    validate_command,
    ValidationError,
)

try:
    user_path = validate_path(user_input, "file_path", allow_relative=False)
except ValidationError as e:
    logger.warning("invalid path provided: %s", e)
```

### 3. **Resource Lifecycle Management**

**Problem**: Thread pool executor not properly shut down on process exit, leading to resource leaks.

**Solution**: Added `atexit` handler in `acp_adapter/server.py` for graceful executor shutdown.

**Pattern**:
```python
import atexit
from concurrent.futures import ThreadPoolExecutor

_executor = ThreadPoolExecutor(max_workers=4)

def _shutdown_executor() -> None:
    _executor.shutdown(wait=True, timeout=5)
    logger.debug("executor shut down gracefully")

atexit.register(_shutdown_executor)
```

### 4. **Dependency Import Hardening**

**Problem**: Platform-specific imports (fcntl, msvcrt) silently fail with generic exceptions, hiding actual import errors.

**Solution**: Specific `ImportError` handling with debug logging.

**Pattern**:
```python
try:
    import fcntl
except ImportError as e:
    logger.debug("fcntl not available (expected on Windows): %s", e)
    fcntl = None
```

## Critical Production Paths

### Path 1: Credential Management
**File**: `hercules_cli/auth.py`
- **Requirement**: Cross-process file locking using fcntl/msvcrt
- **Hardening**: Specific exception handling for platform-specific imports
- **Testing**: Verify concurrent auth.json writes don't corrupt state

### Path 2: Context Compression
**File**: `agent/context_compressor.py`
- **Requirement**: Graceful degradation when compression fails
- **Hardening**: Specific error classification for recoverable vs non-recoverable failures
- **Testing**: Test database unavailability, state corruption scenarios

### Path 3: Tool Execution
**File**: `agent/tool_executor.py`
- **Requirement**: Reliable tool invocation with proper error propagation
- **Hardening**: Implement specific exception hierarchies, add contextual logging
- **Testing**: Test tool failures at each execution stage

### Path 4: Gateway Server
**File**: `gateway/run.py`
- **Requirement**: Media extraction from tool outputs without data loss
- **Hardening**: Specific JSON parsing exception handling
- **Testing**: Test malformed JSON, edge cases

## Security Patterns

### Input Validation
All user-provided inputs should be validated at the API boundary:

```python
# In tool or command handler
from agent.input_validation import validate_string, validate_path

def handle_file_operation(user_path: str):
    try:
        safe_path = validate_path(
            user_path,
            "file_path",
            allow_relative=True,
            must_exist=False,
        )
    except ValidationError as e:
        return error_response(f"Invalid path: {e.reason}")
    
    # Now safe_path is validated
    return process_file(safe_path)
```

### Command Execution
Never pass unsanitized user input to subprocess:

```python
from agent.input_validation import validate_command

try:
    cmd = validate_command(user_input, "command")
    result = subprocess.run(cmd.split(), capture_output=True)
except ValidationError as e:
    logger.warning("rejected unsafe command: %s", e.reason)
```

## Observability Patterns

### Structured Logging
Use consistent logging patterns for debugging and monitoring:

```python
import logging
logger = logging.getLogger(__name__)

# Include context in all logs
logger.info(
    "operation completed",
    extra={
        "session_id": session_id,
        "duration_ms": elapsed_ms,
        "tool_name": tool_name,
    }
)

# Use appropriate levels
logger.debug("low-level diagnostic info")      # Development/detailed debugging
logger.info("significant state changes")       # Normal operations
logger.warning("recoverable error conditions") # Configuration issues
logger.error("service-level failures")         # Critical failures
```

### Error Context
Always include error context in exception logs:

```python
try:
    result = api_call()
except RequestException as e:
    logger.exception(
        "API call failed",
        extra={
            "endpoint": endpoint,
            "status_code": e.response.status_code if e.response else None,
            "retry_count": retry_count,
        }
    )
```

## Testing Checklist

- [ ] Error paths with no network connectivity
- [ ] Malformed input data (JSON, paths, commands)
- [ ] Concurrent access to shared resources (auth.json, session db)
- [ ] Resource exhaustion (large files, deep recursion)
- [ ] Timeout and cancellation scenarios
- [ ] Permission errors and access violations
- [ ] Credential rotation and expiry handling

## Deployment Checklist

- [ ] Enable debug logging in non-production environments
- [ ] Configure centralized log aggregation
- [ ] Set up alerts for error rate thresholds
- [ ] Test graceful shutdown procedures
- [ ] Verify resource cleanup on exit
- [ ] Monitor thread pool saturation
- [ ] Test credential refresh under load
- [ ] Validate compression failure recovery

## Monitoring Metrics

Key metrics to track in production:

1. **Error Rate**: Count of exceptions by type and source
2. **Tool Success Rate**: Percentage of successful tool executions
3. **Latency**: P50, P95, P99 for critical operations
4. **Resource Usage**: Thread pool utilization, memory, disk I/O
5. **Compression Success**: Compression failure rate and recovery
6. **Credential Health**: Token refresh success rate, expiry warnings

## Future Improvements

1. **Structured Error Taxonomy**: Create explicit exception hierarchy for all error types
2. **Circuit Breaker Pattern**: Implement for external API calls to prevent cascading failures
3. **Metrics Collection**: Add instrumentation for key operations
4. **Health Check Endpoints**: Expose readiness/liveness probes for orchestration
5. **Configuration Validation**: Pre-flight checks for required settings
6. **Distributed Tracing**: Add request ID correlation across processes

## References

- [Python Error Handling Best Practices](https://docs.python.org/3/library/exceptions.html)
- [OWASP Input Validation](https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html)
- [Structured Logging](https://www.python-logging.org/)
- [Secure Coding Guidelines](https://owasp.org/www-project-secure-coding-practices-quick-reference-guide/)
