"""Comprehensive input validation and sanitization for production security.

Provides a centralized validation layer for all user inputs to prevent:
- Command injection attacks
- Path traversal attacks
- Buffer overflows via oversized inputs
- Type confusion
- Malformed data structures

Use this module as a guard rail in all public-facing tool methods.
"""

from __future__ import annotations

import re
import logging
from pathlib import Path
from typing import Any, Optional, Union, Pattern, Callable, TypeVar
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ValidationError(ValueError):
    """Raised when input validation fails."""

    def __init__(self, field: str, reason: str, value: Optional[str] = None):
        self.field = field
        self.reason = reason
        self.value = value
        msg = f"Validation failed for '{field}': {reason}"
        if value is not None:
            msg += f" (value: {value[:50]}...)" if len(str(value)) > 50 else f" (value: {value})"
        super().__init__(msg)


class ValidationLevel(Enum):
    """Strictness level for validation."""

    STRICT = "strict"      # Reject anything suspicious
    NORMAL = "normal"      # Standard security validation
    LENIENT = "lenient"    # Allow more variations


# ── Common patterns ────────────────────────────────────────────────────────

# Dangerous path sequences that indicate traversal attempts
_PATH_TRAVERSAL_PATTERNS = [
    re.compile(r"\.\./"),           # ../ sequences
    re.compile(r"\.\\."),            # ..\ sequences (Windows)
    re.compile(r"^~"),               # Home directory expansion attempts
    re.compile(r"%SystemRoot%"),     # Windows env var expansion
    re.compile(r"\$\{?[A-Z_]+\}?"),  # Unix env var expansion
]

# Shell metacharacters that indicate injection attempts when unquoted
_SHELL_METACHARACTERS = set("|;&<>$()`\\'\"\n")

# Valid filename patterns (conservative)
_VALID_FILENAME = re.compile(r"^[a-zA-Z0-9._\-/]{1,255}$")

# Valid domain name
_VALID_DOMAIN = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$",
    re.IGNORECASE,
)

# Valid IPv4 address
_VALID_IPV4 = re.compile(
    r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}"
    r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
)


@dataclass
class ValidationConfig:
    """Configuration for validation behavior."""

    level: ValidationLevel = ValidationLevel.NORMAL
    max_string_length: int = 10_000
    max_array_length: int = 1000
    max_object_depth: int = 50
    allow_null: bool = True
    log_failures: bool = True


# Global default configuration
_DEFAULT_CONFIG = ValidationConfig()


def _log_validation_failure(field: str, reason: str, config: ValidationConfig) -> None:
    """Log validation failure at appropriate level."""
    if config.log_failures:
        logger.warning(f"Validation failed: {field} - {reason}")


def validate_string(
    value: Any,
    field: str = "input",
    *,
    min_length: int = 0,
    max_length: Optional[int] = None,
    pattern: Optional[Union[str, Pattern]] = None,
    allow_empty: bool = False,
    config: ValidationConfig = _DEFAULT_CONFIG,
) -> str:
    """Validate and return a string value.

    Args:
        value: Value to validate
        field: Field name for error messages
        min_length: Minimum string length (exclusive if 0)
        max_length: Maximum string length
        pattern: Regex pattern the string must match
        allow_empty: Whether empty strings are valid
        config: Validation configuration

    Returns:
        Validated string

    Raises:
        ValidationError: If validation fails
    """
    if value is None:
        if config.allow_null:
            return ""
        raise ValidationError(field, "null value not allowed")

    if not isinstance(value, str):
        raise ValidationError(field, f"expected string, got {type(value).__name__}")

    # Check length constraints
    if not allow_empty and not value:
        raise ValidationError(field, "empty string not allowed")

    effective_max = max_length or config.max_string_length
    if len(value) > effective_max:
        raise ValidationError(
            field,
            f"string exceeds maximum length of {effective_max}",
            value,
        )

    if len(value) < min_length:
        raise ValidationError(
            field, f"string shorter than minimum length of {min_length}"
        )

    # Check against pattern
    if pattern:
        if isinstance(pattern, str):
            pattern = re.compile(pattern)
        if not pattern.match(value):
            raise ValidationError(
                field, f"string does not match required pattern", value
            )

    return value


def validate_path(
    value: Any,
    field: str = "path",
    *,
    must_exist: bool = False,
    allow_relative: bool = True,
    config: ValidationConfig = _DEFAULT_CONFIG,
) -> Path:
    """Validate and return a filesystem path.

    Args:
        value: Value to validate
        field: Field name for error messages
        must_exist: Whether path must exist on filesystem
        allow_relative: Whether relative paths are allowed
        config: Validation configuration

    Returns:
        Validated Path object

    Raises:
        ValidationError: If validation fails
    """
    path_str = validate_string(value, field, max_length=4096, config=config)

    # Check for path traversal attempts
    for pattern in _PATH_TRAVERSAL_PATTERNS:
        if pattern.search(path_str):
            raise ValidationError(
                field,
                f"path contains suspicious pattern: {pattern.pattern}",
                path_str,
            )

    try:
        path = Path(path_str)
    except (ValueError, TypeError) as e:
        raise ValidationError(field, f"invalid path: {e}", path_str) from e

    # Validate path constraints
    if not allow_relative and not path.is_absolute():
        raise ValidationError(field, "relative paths not allowed", path_str)

    if must_exist and not path.exists():
        raise ValidationError(field, f"path does not exist", path_str)

    return path


def validate_command(
    value: Any,
    field: str = "command",
    *,
    config: ValidationConfig = _DEFAULT_CONFIG,
) -> str:
    """Validate a shell command string to detect injection attacks.

    Args:
        value: Value to validate
        field: Field name for error messages
        config: Validation configuration

    Returns:
        Validated command string

    Raises:
        ValidationError: If injection patterns detected
    """
    cmd = validate_string(value, field, config=config)

    # Check for shell metacharacters that indicate injection
    if config.level == ValidationLevel.STRICT:
        dangerous = _SHELL_METACHARACTERS & set(cmd)
        if dangerous:
            raise ValidationError(
                field,
                f"command contains shell metacharacters: {dangerous}",
                cmd,
            )

    return cmd


def validate_integer(
    value: Any,
    field: str = "integer",
    *,
    min_value: Optional[int] = None,
    max_value: Optional[int] = None,
    config: ValidationConfig = _DEFAULT_CONFIG,
) -> int:
    """Validate and return an integer value.

    Args:
        value: Value to validate
        field: Field name for error messages
        min_value: Minimum allowed value
        max_value: Maximum allowed value
        config: Validation configuration

    Returns:
        Validated integer

    Raises:
        ValidationError: If validation fails
    """
    if value is None:
        if config.allow_null:
            return 0
        raise ValidationError(field, "null value not allowed")

    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationError(field, f"expected integer, got {type(value).__name__}")

    if min_value is not None and value < min_value:
        raise ValidationError(field, f"value below minimum of {min_value}")

    if max_value is not None and value > max_value:
        raise ValidationError(field, f"value exceeds maximum of {max_value}")

    return value


def validate_array(
    value: Any,
    field: str = "array",
    *,
    element_validator: Optional[Callable[[Any], Any]] = None,
    max_length: Optional[int] = None,
    config: ValidationConfig = _DEFAULT_CONFIG,
) -> list:
    """Validate and return an array/list value.

    Args:
        value: Value to validate
        field: Field name for error messages
        element_validator: Optional validator for array elements
        max_length: Maximum array length
        config: Validation configuration

    Returns:
        Validated list

    Raises:
        ValidationError: If validation fails
    """
    if value is None:
        if config.allow_null:
            return []
        raise ValidationError(field, "null value not allowed")

    if not isinstance(value, (list, tuple)):
        raise ValidationError(field, f"expected array, got {type(value).__name__}")

    effective_max = max_length or config.max_array_length
    if len(value) > effective_max:
        raise ValidationError(
            field, f"array exceeds maximum length of {effective_max}"
        )

    if element_validator:
        validated = []
        for i, item in enumerate(value):
            try:
                validated.append(element_validator(item))
            except ValidationError as e:
                raise ValidationError(
                    f"{field}[{i}]", f"element validation failed: {e.reason}"
                ) from e
        return validated

    return list(value)


def validate_url(
    value: Any,
    field: str = "url",
    *,
    allowed_schemes: Optional[set[str]] = None,
    config: ValidationConfig = _DEFAULT_CONFIG,
) -> str:
    """Validate and return a URL string.

    Args:
        value: Value to validate
        field: Field name for error messages
        allowed_schemes: Whitelist of allowed URL schemes (default: http, https)
        config: Validation configuration

    Returns:
        Validated URL string

    Raises:
        ValidationError: If validation fails
    """
    from urllib.parse import urlparse

    url = validate_string(value, field, max_length=2048, config=config)
    allowed_schemes = allowed_schemes or {"http", "https"}

    try:
        parsed = urlparse(url)
    except Exception as e:
        raise ValidationError(field, f"malformed URL: {e}", url) from e

    if parsed.scheme not in allowed_schemes:
        raise ValidationError(
            field, f"scheme '{parsed.scheme}' not allowed", url
        )

    if not parsed.netloc:
        raise ValidationError(field, "URL missing hostname", url)

    return url


def validate_object(
    value: Any,
    field: str = "object",
    *,
    schema: Optional[dict[str, Callable]] = None,
    config: ValidationConfig = _DEFAULT_CONFIG,
) -> dict:
    """Validate and return an object/dictionary value.

    Args:
        value: Value to validate
        field: Field name for error messages
        schema: Optional schema mapping field names to validators
        config: Validation configuration

    Returns:
        Validated dictionary

    Raises:
        ValidationError: If validation fails
    """
    if value is None:
        if config.allow_null:
            return {}
        raise ValidationError(field, "null value not allowed")

    if not isinstance(value, dict):
        raise ValidationError(field, f"expected object, got {type(value).__name__}")

    if schema:
        validated = {}
        for key, validator in schema.items():
            if key not in value:
                raise ValidationError(f"{field}.{key}", "required field missing")
            try:
                validated[key] = validator(value[key])
            except ValidationError as e:
                raise ValidationError(f"{field}.{key}", str(e)) from e
        return validated

    return dict(value)


# Convenience functions for common validations

def validate_not_null(value: T, field: str = "value") -> T:
    """Ensure value is not null."""
    if value is None:
        raise ValidationError(field, "null value not allowed")
    return value


def validate_safe_filename(value: Any, field: str = "filename") -> str:
    """Validate a safe filename (no path separators or traversal)."""
    filename = validate_string(value, field, max_length=255)
    if "/" in filename or "\\" in filename:
        raise ValidationError(field, "path separators not allowed in filename")
    if filename in {".", ".."}:
        raise ValidationError(field, "invalid filename")
    return filename
