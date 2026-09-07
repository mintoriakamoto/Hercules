"""Error handling standards and utilities for production-grade code.

Provides structured exception hierarchies, decorators, and patterns that ensure:
- Specific exception types instead of bare `except Exception`
- Contextual logging at appropriate severity levels
- Proper error recovery strategies
- Audit trails for debugging production issues

This module codifies best practices across the codebase.
"""

from __future__ import annotations

import functools
import logging
import sys
import traceback
from contextlib import contextmanager
from enum import Enum
from typing import Any, Callable, Generator, Optional, Type, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ErrorSeverity(Enum):
    """Severity classification for errors."""

    CRITICAL = "critical"    # Service halt required
    ERROR = "error"          # Service degradation
    WARNING = "warning"      # Recoverable issue
    INFO = "info"            # Informational only


class HerculesException(Exception):
    """Base exception for all Hercules errors."""

    def __init__(
        self,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        context: Optional[dict[str, Any]] = None,
    ):
        self.message = message
        self.severity = severity
        self.context = context or {}
        super().__init__(message)

    def log(self, logger_instance: logging.Logger) -> None:
        """Log the exception with appropriate severity."""
        level = {
            ErrorSeverity.CRITICAL: logging.CRITICAL,
            ErrorSeverity.ERROR: logging.ERROR,
            ErrorSeverity.WARNING: logging.WARNING,
            ErrorSeverity.INFO: logging.INFO,
        }.get(self.severity, logging.ERROR)

        logger_instance.log(
            level,
            f"{self.__class__.__name__}: {self.message}",
            extra={"context": self.context},
            exc_info=sys.exc_info()[2] is not None,
        )


class ConfigurationError(HerculesException):
    """Configuration or initialization failed."""

    def __init__(self, message: str, context: Optional[dict] = None):
        super().__init__(message, ErrorSeverity.CRITICAL, context)


class ResourceError(HerculesException):
    """Resource access or allocation failed."""

    def __init__(self, message: str, context: Optional[dict] = None):
        super().__init__(message, ErrorSeverity.ERROR, context)


class RecoverableError(HerculesException):
    """Transient error that can be retried."""

    def __init__(self, message: str, context: Optional[dict] = None):
        super().__init__(message, ErrorSeverity.WARNING, context)


class DataValidationError(HerculesException):
    """Input data validation failed."""

    def __init__(self, message: str, context: Optional[dict] = None):
        super().__init__(message, ErrorSeverity.WARNING, context)


def safe_operation(
    operation_name: str,
    severity: ErrorSeverity = ErrorSeverity.ERROR,
    fallback: Optional[T] = None,
    log_traceback: bool = True,
) -> Callable:
    """Decorator for safe exception handling with logging.

    Args:
        operation_name: Name of the operation for logging
        severity: Error severity level
        fallback: Fallback value on exception
        log_traceback: Whether to log full traceback

    Example:
        @safe_operation("config_load", fallback={})
        def load_config():
            return json.load(open("config.json"))
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return func(*args, **kwargs)
            except HerculesException as e:
                e.log(logger)
                return fallback
            except (OSError, IOError) as e:
                level = logging.ERROR if severity == ErrorSeverity.CRITICAL else logging.WARNING
                logger.log(
                    level,
                    f"{operation_name} failed: file/resource error: {e}",
                    exc_info=log_traceback,
                )
                return fallback
            except (ValueError, TypeError) as e:
                logger.warning(
                    f"{operation_name} failed: data validation error: {e}",
                    exc_info=log_traceback,
                )
                return fallback
            except Exception as e:
                level = logging.ERROR if severity == ErrorSeverity.CRITICAL else logging.WARNING
                logger.log(
                    level,
                    f"{operation_name} failed: unexpected error: {e}",
                    exc_info=log_traceback,
                )
                return fallback

        return wrapper

    return decorator


@contextmanager
def safe_context(
    context_name: str,
    severity: ErrorSeverity = ErrorSeverity.ERROR,
    suppress_exception: bool = False,
) -> Generator[None, None, None]:
    """Context manager for safe operation execution.

    Args:
        context_name: Name of the operation for logging
        severity: Error severity level
        suppress_exception: Whether to suppress the exception

    Example:
        with safe_context("database_transaction"):
            db.execute(query)
    """
    try:
        yield
    except HerculesException as e:
        e.log(logger)
        if not suppress_exception:
            raise
    except (OSError, IOError) as e:
        level = logging.ERROR if severity == ErrorSeverity.CRITICAL else logging.WARNING
        logger.log(
            level,
            f"{context_name}: file/resource error: {e}",
            exc_info=True,
        )
        if not suppress_exception:
            raise ResourceError(f"{context_name}: {e}", {"operation": context_name}) from e
    except (ValueError, TypeError) as e:
        logger.warning(
            f"{context_name}: data validation error: {e}",
            exc_info=True,
        )
        if not suppress_exception:
            raise DataValidationError(f"{context_name}: {e}", {"operation": context_name}) from e
    except Exception as e:
        level = logging.ERROR if severity == ErrorSeverity.CRITICAL else logging.WARNING
        logger.log(
            level,
            f"{context_name}: unexpected error: {e}",
            exc_info=True,
        )
        if not suppress_exception:
            raise


def handle_errors(*exception_types: Type[Exception]) -> Callable:
    """Decorator to handle specific exception types with logging.

    Args:
        exception_types: Exception types to handle

    Example:
        @handle_errors(ValueError, TypeError)
        def process_data(data):
            return int(data)
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except exception_types as e:
                logger.warning(
                    f"{func.__name__} raised {type(e).__name__}: {e}",
                    exc_info=False,
                )
                raise

        return wrapper

    return decorator


def log_exception(
    logger_instance: logging.Logger,
    exc: Exception,
    message: str = "",
    level: int = logging.ERROR,
    context: Optional[dict] = None,
) -> None:
    """Log an exception with context.

    Args:
        logger_instance: Logger to use
        exc: Exception to log
        message: Optional custom message
        level: Logging level
        context: Optional context dict
    """
    if isinstance(exc, HerculesException):
        exc.log(logger_instance)
    else:
        full_message = f"{message}: {exc}" if message else str(exc)
        logger_instance.log(
            level,
            full_message,
            extra={"context": context or {}, "exception_type": type(exc).__name__},
            exc_info=True,
        )


# Common exception patterns

class RetryableError(RecoverableError):
    """Error that should trigger a retry."""

    pass


class TimeoutError(RecoverableError):
    """Operation timed out."""

    pass


class NetworkError(RecoverableError):
    """Network operation failed."""

    pass


class AuthenticationError(HerculesException):
    """Authentication failed."""

    def __init__(self, message: str, context: Optional[dict] = None):
        super().__init__(message, ErrorSeverity.ERROR, context)


class PermissionError(HerculesException):
    """Permission denied."""

    def __init__(self, message: str, context: Optional[dict] = None):
        super().__init__(message, ErrorSeverity.WARNING, context)


# Example usage patterns

def example_safe_operation():
    """Example of using safe_operation decorator."""

    @safe_operation("json_load", fallback={})
    def load_config(path: str) -> dict:
        import json
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    result = load_config("config.json")
    return result


def example_safe_context():
    """Example of using safe_context."""

    def process_data():
        with safe_context("data_processing", severity=ErrorSeverity.ERROR):
            data = {"key": "value"}
            # Process data safely
            return data

    return process_data()
