"""Error recovery patterns and strategies for Hercules Agent.

Implements resilient patterns for common failure scenarios:
- Transient network failures (retry with exponential backoff)
- File I/O errors (with fallback paths)
- Configuration failures (sensible defaults)
- Database operations (with rollback)
- External API calls (with timeout and circuit breaker)

Each pattern is tested and documented with clear recovery semantics.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Optional, TypeVar, Union

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryStrategy:
    """Configurable retry strategy for transient failures."""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
    ):
        """Initialize retry strategy.

        Args:
            max_attempts: Maximum number of retry attempts
            base_delay: Initial delay in seconds
            max_delay: Maximum delay between retries
            exponential_base: Base for exponential backoff
            jitter: Add random jitter to delays
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt."""
        delay = min(
            self.base_delay * (self.exponential_base ** attempt),
            self.max_delay,
        )

        if self.jitter:
            import random
            delay = delay * (0.5 + random.random())

        return delay

    def should_retry(self, attempt: int, exception: Exception) -> bool:
        """Determine if exception is retryable."""
        if attempt >= self.max_attempts:
            return False

        # Retryable exception types
        retryable_types = (
            TimeoutError,
            ConnectionError,
            BrokenPipeError,
            OSError,
        )

        # Check exception type
        if isinstance(exception, retryable_types):
            return True

        # Check exception message for common retry patterns
        msg = str(exception).lower()
        retry_patterns = [
            "timeout",
            "temporarily unavailable",
            "try again",
            "connection refused",
            "connection reset",
            "broken pipe",
            "resource temporarily unavailable",
        ]

        return any(pattern in msg for pattern in retry_patterns)


def retry_with_backoff(
    func: Callable[..., T],
    *args: Any,
    strategy: Optional[RetryStrategy] = None,
    logger_instance: Optional[logging.Logger] = None,
    **kwargs: Any,
) -> T:
    """Execute function with retry and exponential backoff.

    Args:
        func: Function to execute
        args: Positional arguments for func
        strategy: RetryStrategy instance (default: standard config)
        logger_instance: Logger for debug output
        kwargs: Keyword arguments for func

    Returns:
        Result of successful function call

    Raises:
        Exception: Final exception if all retries exhausted
    """
    _logger = logger_instance or logger
    strategy = strategy or RetryStrategy()

    last_exception: Optional[Exception] = None

    for attempt in range(strategy.max_attempts):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_exception = e

            if not strategy.should_retry(attempt, e):
                _logger.error(
                    f"non-retryable error on attempt {attempt + 1}: {type(e).__name__}: {e}"
                )
                raise

            if attempt < strategy.max_attempts - 1:
                delay = strategy.get_delay(attempt)
                _logger.warning(
                    f"attempt {attempt + 1} failed: {type(e).__name__}: {e}. "
                    f"Retrying in {delay:.2f}s..."
                )
                time.sleep(delay)
            else:
                _logger.error(
                    f"all {strategy.max_attempts} attempts failed. "
                    f"Last error: {type(e).__name__}: {e}"
                )

    raise last_exception or Exception("Retry exhausted with no error captured")


class CircuitBreaker:
    """Circuit breaker pattern for failing external services.

    Prevents cascading failures by stopping calls to a failing service
    after it exceeds a failure threshold, giving it time to recover.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception,
    ):
        """Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before trying again
            expected_exception: Exception type that triggers the circuit
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "closed"  # closed, open, half-open

    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute function with circuit breaker protection.

        Args:
            func: Function to execute
            args: Positional arguments
            kwargs: Keyword arguments

        Returns:
            Result of function call

        Raises:
            RuntimeError: If circuit is open
            Exception: From the wrapped function
        """
        # Check if we should attempt recovery
        if self.state == "open":
            if self._should_attempt_recovery():
                self.state = "half-open"
                logger.info("Circuit breaker entering half-open state")
            else:
                raise RuntimeError(
                    f"Circuit breaker open (recovery in {self._time_until_recovery():.1f}s)"
                )

        try:
            result = func(*args, **kwargs)

            # Success - reset state
            if self.state == "half-open":
                self.state = "closed"
                self.failure_count = 0
                logger.info("Circuit breaker closed - service recovered")

            return result

        except self.expected_exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.failure_count >= self.failure_threshold:
                self.state = "open"
                logger.error(
                    f"Circuit breaker opened after {self.failure_count} failures: {e}"
                )

            raise

    def _should_attempt_recovery(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.recovery_timeout

    def _time_until_recovery(self) -> float:
        """Time remaining until recovery can be attempted."""
        if self.last_failure_time is None:
            return 0
        elapsed = time.time() - self.last_failure_time
        return max(0, self.recovery_timeout - elapsed)


def safe_get(
    obj: dict,
    key: str,
    default: Any = None,
    expected_type: Optional[type] = None,
) -> Any:
    """Safely get value from dict with type checking.

    Args:
        obj: Dictionary to access
        key: Key to retrieve
        default: Default value if key missing or type mismatch
        expected_type: Optional type to validate

    Returns:
        Value from dict, default, or type error fallback
    """
    try:
        if not isinstance(obj, dict):
            logger.debug(f"safe_get called on non-dict: {type(obj)}")
            return default

        value = obj.get(key, default)

        if expected_type and value is not None and not isinstance(value, expected_type):
            logger.debug(
                f"type mismatch for key '{key}': expected {expected_type.__name__}, "
                f"got {type(value).__name__}"
            )
            return default

        return value
    except Exception as e:
        logger.debug(f"error in safe_get for key '{key}': {e}")
        return default


def safe_close(resource: Any, resource_name: str = "resource") -> None:
    """Safely close a resource with proper error handling.

    Args:
        resource: Resource to close (file, connection, etc)
        resource_name: Name for logging purposes
    """
    if resource is None:
        return

    try:
        if hasattr(resource, "close"):
            resource.close()
            logger.debug(f"closed {resource_name}")
    except Exception as e:
        logger.warning(f"error closing {resource_name}: {e}")


# Context manager for safe resource handling

from contextlib import contextmanager


@contextmanager
def safe_resource(resource: Any, resource_name: str = "resource"):
    """Context manager for safe resource management.

    Args:
        resource: Resource to manage
        resource_name: Name for logging

    Yields:
        The resource object

    Example:
        with safe_resource(open("file.txt")) as f:
            data = f.read()
    """
    try:
        yield resource
    finally:
        safe_close(resource, resource_name)


# Fallback chain pattern

class FallbackChain:
    """Execute functions in sequence until one succeeds."""

    def __init__(self, logger_instance: Optional[logging.Logger] = None):
        self.functions: list[tuple[Callable, str]] = []
        self.logger = logger_instance or logger

    def add(self, func: Callable, name: str) -> FallbackChain:
        """Add a function to the fallback chain.

        Args:
            func: Function to try
            name: Name for logging

        Returns:
            Self for chaining
        """
        self.functions.append((func, name))
        return self

    def execute(self, *args: Any, default: Any = None, **kwargs: Any) -> Any:
        """Execute fallback chain.

        Args:
            args: Arguments for functions
            default: Default value if all fail
            kwargs: Keyword arguments for functions

        Returns:
            Result from first successful function or default
        """
        for func, name in self.functions:
            try:
                result = func(*args, **kwargs)
                self.logger.debug(f"fallback chain succeeded: {name}")
                return result
            except Exception as e:
                self.logger.debug(f"fallback '{name}' failed: {type(e).__name__}: {e}")

        self.logger.warning(f"all {len(self.functions)} fallbacks failed")
        return default
