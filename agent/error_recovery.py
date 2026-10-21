"""Sophisticated error recovery and self-healing.

Implements:
- Error classification and diagnosis
- Automatic recovery strategies
- Learning from failures
- Graceful degradation
"""

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional, Any, List
import traceback


class ErrorSeverity(Enum):
    """Error severity levels."""
    CRITICAL = "critical"  # Stop immediately
    HIGH = "high"  # Try recovery, then fail
    MEDIUM = "medium"  # Attempt recovery
    LOW = "low"  # Log and continue
    INFO = "info"  # Informational


class ErrorCategory(Enum):
    """Error categories for diagnosis."""
    SYNTAX = "syntax"
    IMPORT = "import"
    RUNTIME = "runtime"
    TIMEOUT = "timeout"
    MEMORY = "memory"
    PERMISSION = "permission"
    API = "api"
    UNKNOWN = "unknown"


@dataclass
class ErrorDiagnosis:
    """Diagnosed error information."""
    error: Exception
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    recovery_suggestions: List[str]
    traceback_str: str


class ErrorRecovery:
    """Intelligent error recovery system."""

    def __init__(self):
        self.recovery_strategies: dict = {}
        self.error_history: List[ErrorDiagnosis] = []

    def diagnose(self, error: Exception) -> ErrorDiagnosis:
        """Diagnose error and suggest recovery."""
        error_str = str(error)
        traceback_str = traceback.format_exc()

        # Classify error
        category, severity = self._classify(error, error_str)

        # Generate recovery suggestions
        suggestions = self._suggest_recovery(category, error_str)

        diagnosis = ErrorDiagnosis(
            error=error,
            category=category,
            severity=severity,
            message=error_str,
            recovery_suggestions=suggestions,
            traceback_str=traceback_str,
        )

        self.error_history.append(diagnosis)
        return diagnosis

    def _classify(self, error: Exception, msg: str) -> tuple:
        """Classify error type and severity."""
        error_type = type(error).__name__

        if error_type == "SyntaxError":
            return ErrorCategory.SYNTAX, ErrorSeverity.CRITICAL

        if error_type == "ImportError" or error_type == "ModuleNotFoundError":
            return ErrorCategory.IMPORT, ErrorSeverity.HIGH

        if error_type == "TimeoutError":
            return ErrorCategory.TIMEOUT, ErrorSeverity.HIGH

        if error_type == "MemoryError":
            return ErrorCategory.MEMORY, ErrorSeverity.CRITICAL

        if error_type == "PermissionError":
            return ErrorCategory.PERMISSION, ErrorSeverity.HIGH

        if "API" in error_type or "api" in msg.lower():
            return ErrorCategory.API, ErrorSeverity.HIGH

        return ErrorCategory.RUNTIME, ErrorSeverity.MEDIUM

    def _suggest_recovery(self, category: ErrorCategory, msg: str) -> List[str]:
        """Suggest recovery actions."""
        suggestions = {
            ErrorCategory.SYNTAX: [
                "Review syntax around the error location",
                "Check for matching brackets and quotes",
                "Run formatter to fix spacing",
            ],
            ErrorCategory.IMPORT: [
                "Check if package is installed",
                "Verify package name spelling",
                "Install missing dependency",
            ],
            ErrorCategory.TIMEOUT: [
                "Increase timeout limit",
                "Break task into smaller steps",
                "Optimize code for speed",
            ],
            ErrorCategory.MEMORY: [
                "Reduce context size",
                "Process data in batches",
                "Clear caches and rerun",
            ],
            ErrorCategory.PERMISSION: [
                "Check file/directory permissions",
                "Run with elevated privileges if needed",
                "Use alternative file path",
            ],
            ErrorCategory.API: [
                "Check API rate limits",
                "Verify API credentials",
                "Try request again with backoff",
            ],
            ErrorCategory.RUNTIME: [
                "Simplify the operation",
                "Add input validation",
                "Wrap in try-except",
            ],
            ErrorCategory.UNKNOWN: [
                "Review error message carefully",
                "Check documentation",
                "Try alternative approach",
            ],
        }
        return suggestions.get(category, ["Check error message", "Try alternative"])

    def attempt_recovery(
        self,
        diagnosis: ErrorDiagnosis,
        recovery_fn: Optional[Callable] = None,
    ) -> bool:
        """Attempt to recover from error.

        Args:
            diagnosis: Error diagnosis
            recovery_fn: Custom recovery function

        Returns:
            True if recovered, False otherwise
        """
        if recovery_fn:
            try:
                recovery_fn()
                return True
            except Exception:
                pass

        # Try default recovery based on category
        if diagnosis.category == ErrorCategory.TIMEOUT:
            return self._recover_timeout()
        elif diagnosis.category == ErrorCategory.MEMORY:
            return self._recover_memory()
        elif diagnosis.category == ErrorCategory.IMPORT:
            return self._recover_import(str(diagnosis.error))

        return False

    def _recover_timeout(self) -> bool:
        """Attempt timeout recovery."""
        # Could trigger: longer timeout, simplify task, etc.
        return False

    def _recover_memory(self) -> bool:
        """Attempt memory recovery."""
        # Could trigger: garbage collection, cache clearing, etc.
        return False

    def _recover_import(self, error_msg: str) -> bool:
        """Attempt import recovery."""
        # Could trigger: pip install, alternative import, etc.
        return False

    def get_failure_report(self) -> str:
        """Get summary of recent failures."""
        if not self.error_history:
            return "No errors recorded"

        report = ["Recent Errors:", ""]
        for i, diagnosis in enumerate(self.error_history[-5:], 1):
            report.append(
                f"{i}. [{diagnosis.severity.value}] {diagnosis.category.value}: "
                f"{diagnosis.message[:80]}"
            )

        return "\n".join(report)


__all__ = ["ErrorRecovery", "ErrorDiagnosis", "ErrorSeverity", "ErrorCategory"]
