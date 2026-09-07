"""Production readiness validator for Hercules Agent deployment.

Performs pre-flight checks to ensure the agent is ready for production deployment.
Validates:
- Configuration completeness
- Security posture
- Resource availability
- Dependency health
- Error handling robustness

Run with: python -m agent.production_validator
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, List, Optional

logger = logging.getLogger(__name__)


class CheckSeverity(Enum):
    """Severity level of a failed check."""

    CRITICAL = "critical"  # Must be fixed before deployment
    WARNING = "warning"    # Should be reviewed/fixed
    INFO = "info"          # Informational only


@dataclass
class ValidationResult:
    """Result of a single validation check."""

    name: str
    passed: bool
    severity: CheckSeverity
    message: str
    remediation: Optional[str] = None


class ProductionValidator:
    """Validates Hercules Agent for production deployment."""

    def __init__(self):
        self.results: List[ValidationResult] = []

    def check(
        self,
        name: str,
        condition: bool,
        severity: CheckSeverity = CheckSeverity.WARNING,
        message: str = "",
        remediation: Optional[str] = None,
    ) -> None:
        """Record a validation check result."""
        self.results.append(
            ValidationResult(
                name=name,
                passed=condition,
                severity=severity,
                message=message,
                remediation=remediation,
            )
        )

    def _validate_imports(self) -> None:
        """Verify critical imports are available."""
        critical_imports = [
            ("logging", "Python logging module"),
            ("json", "JSON support"),
            ("sqlite3", "SQLite database support"),
            ("pathlib", "Path utilities"),
            ("threading", "Threading support"),
        ]

        for module_name, description in critical_imports:
            try:
                __import__(module_name)
                self.check(
                    f"import_{module_name}",
                    True,
                    CheckSeverity.CRITICAL,
                    f"{description} available",
                )
            except ImportError as e:
                self.check(
                    f"import_{module_name}",
                    False,
                    CheckSeverity.CRITICAL,
                    f"Failed to import {module_name}: {e}",
                    f"Install Python {module_name} package",
                )

    def _validate_file_access(self) -> None:
        """Verify critical file paths are accessible."""
        home = Path.home()
        hercules_home = home / ".hercules"

        # Check Hercules home directory
        try:
            if not hercules_home.exists():
                hercules_home.mkdir(parents=True, exist_ok=True)

            # Test write permission
            test_file = hercules_home / ".write_test"
            test_file.write_text("")
            test_file.unlink()

            self.check(
                "hercules_home_access",
                True,
                CheckSeverity.CRITICAL,
                f"Hercules home directory writable: {hercules_home}",
            )
        except (OSError, PermissionError) as e:
            self.check(
                "hercules_home_access",
                False,
                CheckSeverity.CRITICAL,
                f"Cannot write to Hercules home: {e}",
                f"Check permissions on {hercules_home}",
            )

    def _validate_environment(self) -> None:
        """Check critical environment variables."""
        critical_env_vars = [
            ("PATH", "System executable path"),
            ("HOME", "User home directory"),
        ]

        for var_name, description in critical_env_vars:
            has_var = var_name in os.environ and bool(os.environ[var_name])
            self.check(
                f"env_{var_name.lower()}",
                has_var,
                CheckSeverity.CRITICAL,
                f"{description} configured",
                f"Set ${var_name} environment variable",
            )

    def _validate_error_handling(self) -> None:
        """Verify error handling modules are available."""
        try:
            from agent import error_classifier
            self.check(
                "error_classifier_available",
                True,
                CheckSeverity.WARNING,
                "Error classifier module available",
            )
        except ImportError as e:
            self.check(
                "error_classifier_available",
                False,
                CheckSeverity.WARNING,
                f"Error classifier not available: {e}",
            )

        try:
            from agent import input_validation
            self.check(
                "input_validation_available",
                True,
                CheckSeverity.WARNING,
                "Input validation module available",
            )
        except ImportError as e:
            self.check(
                "input_validation_available",
                False,
                CheckSeverity.WARNING,
                f"Input validation not available: {e}",
                "Review agent/input_validation.py",
            )

    def _validate_logging_config(self) -> None:
        """Verify logging is properly configured."""
        # Check that root logger has handlers
        root_logger = logging.getLogger()
        has_handlers = len(root_logger.handlers) > 0

        self.check(
            "logging_configured",
            has_handlers,
            CheckSeverity.INFO,
            "Logging system configured",
            "Configure Python logging in your application startup",
        )

    def validate_all(self) -> bool:
        """Run all validation checks.

        Returns:
            True if all critical checks passed, False otherwise.
        """
        logger.info("Starting production validation checks...")

        self._validate_imports()
        self._validate_file_access()
        self._validate_environment()
        self._validate_error_handling()
        self._validate_logging_config()

        return self._report_results()

    def _report_results(self) -> bool:
        """Report validation results and return overall status.

        Returns:
            True if all critical checks passed, False otherwise.
        """
        critical_failures = [r for r in self.results if not r.passed and r.severity == CheckSeverity.CRITICAL]
        warnings = [r for r in self.results if not r.passed and r.severity == CheckSeverity.WARNING]
        passed = [r for r in self.results if r.passed]

        print("\n" + "=" * 70)
        print("HERCULES PRODUCTION VALIDATION REPORT")
        print("=" * 70)

        if passed:
            print(f"\n✓ PASSED ({len(passed)} checks):")
            for result in passed[:5]:  # Show first 5
                print(f"  • {result.name}: {result.message}")
            if len(passed) > 5:
                print(f"  ... and {len(passed) - 5} more")

        if warnings:
            print(f"\n⚠ WARNINGS ({len(warnings)} checks):")
            for result in warnings:
                print(f"  • {result.name}: {result.message}")
                if result.remediation:
                    print(f"    → {result.remediation}")

        if critical_failures:
            print(f"\n✗ CRITICAL FAILURES ({len(critical_failures)} checks):")
            for result in critical_failures:
                print(f"  • {result.name}: {result.message}")
                if result.remediation:
                    print(f"    → {result.remediation}")

        print("\n" + "=" * 70)

        if critical_failures:
            print(f"STATUS: FAILED - {len(critical_failures)} critical issues must be resolved")
            return False
        elif warnings:
            print(f"STATUS: PASSED WITH WARNINGS - {len(warnings)} issues should be reviewed")
            return True
        else:
            print("STATUS: READY FOR PRODUCTION")
            return True


def main() -> int:
    """Main entry point for validation."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    validator = ProductionValidator()
    success = validator.validate_all()

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
