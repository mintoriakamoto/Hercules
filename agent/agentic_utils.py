"""Agent runtime utilities — overlay loading, correlation, and sanitization.

MIT-licensed implementations inspired by agentic-soc-platform patterns.
"""

import ast
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import util
from pathlib import Path
from typing import Any, Dict, List, Optional, Type


# ============================================================================
# Dynamic Module Loader — Script Discovery and Loading
# ============================================================================

@dataclass(frozen=True)
class ModuleDefinition:
    """Metadata for a discovered module class."""
    name: str
    path: Path
    module_class: Type


def load_module_from_file(path: Path) -> object:
    """Load a Python file as a dynamically-named module.
    
    Creates a unique module name based on file path to avoid collisions
    when loading multiple similar scripts.
    """
    resolved = Path(path).resolve()
    # Use path hash to create unique module name
    path_hash = hashlib.md5(str(resolved).encode()).hexdigest()[:8]
    module_name = f"_agent_module_{resolved.stem}_{path_hash}"
    
    spec = util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot create module spec for: {path}")
    
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def get_class_from_ast(source_code: str, class_name: str) -> bool:
    """Parse source code and check if class exists (AST analysis)."""
    try:
        tree = ast.parse(source_code)
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                return True
    except SyntaxError:
        pass
    return False


def has_relative_imports(source_code: str) -> bool:
    """Check if source uses relative imports (AST analysis)."""
    try:
        tree = ast.parse(source_code)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level > 0:
                return True
    except SyntaxError:
        pass
    return False


def load_module_class(
    path: Path,
    class_name: str,
    base_class: Type,
) -> Optional[ModuleDefinition]:
    """Load and validate a module class from a file.
    
    Performs pre-flight checks:
    - Verifies class exists in source
    - Rejects files with relative imports (encapsulation)
    - Validates inheritance from base_class
    
    Args:
        path: Python file to load
        class_name: Class name to find
        base_class: Required parent class
        
    Returns:
        ModuleDefinition on success, None if class not found
        
    Raises:
        ImportError: If relative imports found
        TypeError: If class doesn't inherit from base_class
    """
    path = Path(path)
    source = path.read_text(encoding='utf-8')
    
    # Pre-flight checks via AST
    if not get_class_from_ast(source, class_name):
        return None
    
    if has_relative_imports(source):
        raise ImportError(f"Relative imports forbidden in: {path}")
    
    # Load module
    module = load_module_from_file(path)
    loaded_class = getattr(module, class_name, None)
    
    if loaded_class is None:
        return None
    
    if not issubclass(loaded_class, base_class):
        raise TypeError(
            f"{path}: {class_name} must subclass {base_class.__name__}"
        )
    
    loaded_class.SCRIPT_PATH = path
    class_name_attr = getattr(loaded_class, "NAME", "") or path.stem
    
    return ModuleDefinition(name=class_name_attr, path=path, module_class=loaded_class)


def discover_modules_in_directory(
    directory: Path,
    class_name: str,
    base_class: Type,
) -> List[ModuleDefinition]:
    """Scan directory for module classes.
    
    Finds all *.py files (except __init__.py) and attempts to load
    the specified class. Non-conforming files are logged but don't
    halt scanning.
    
    Args:
        directory: Directory to scan
        class_name: Class to find
        base_class: Required parent class
        
    Returns:
        List of successfully loaded ModuleDefinition objects
    """
    directory = Path(directory)
    if not directory.exists():
        return []

    modules = []
    for path in sorted(directory.glob("*.py")):
        if path.name == "__init__.py":
            continue
        try:
            defn = load_module_class(path, class_name, base_class)
            if defn:
                modules.append(defn)
        except (ImportError, TypeError) as e:
            import logging
            logging.getLogger(__name__).debug(
                f"Could not load {path}: {e}"
            )
    
    return modules


def resolve_overlaid_modules(*directories: Path) -> List[Path]:
    """Resolve multiple directories with overlay semantics.
    
    When a module appears in multiple directories, the version from
    the last directory takes precedence. Useful for:
    - Base modules in /etc/agent/
    - User overrides in ~/agent/
    - Project-specific in ./.agent/
    
    Args:
        *directories: Directories to overlay (later = higher priority)
        
    Returns:
        List of Path objects, sorted by filename (unique names only)
    """
    modules_by_name = {}
    for directory in directories:
        directory = Path(directory)
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.py")):
            if path.name == "__init__.py":
                continue
            # Later directory wins (overlay semantics)
            modules_by_name[path.name] = path
    
    return [modules_by_name[name] for name in sorted(modules_by_name)]


# ============================================================================
# Event Correlation — Time-Bucketed Deterministic IDs
# ============================================================================

def bucket_timestamp(dt: Optional[datetime], window: str) -> str:
    """Normalize a timestamp to a correlation window.
    
    Buckets timestamps to enable grouping of related events within
    a time period. E.g., "24h" window means all events in a calendar
    day get the same bucket.
    
    Supported windows: "1m", "5m", "15m", "1h", "6h", "24h", "1d"
    
    Args:
        dt: Timestamp (defaults to now in UTC)
        window: Bucketing window (e.g., "24h")
        
    Returns:
        Normalized timestamp string (YYYYMMDDHHmm format)
    """
    if dt is None:
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    # Minute buckets
    if window.endswith("m"):
        minutes = int(window[:-1])
        bucket_minute = (dt.minute // minutes) * minutes
        return dt.replace(minute=bucket_minute, second=0, microsecond=0)\
            .strftime("%Y%m%d%H%M")
    
    # Hour buckets
    if window.endswith("h"):
        hours = int(window[:-1])
        if hours >= 24:
            # For 24+ hour windows, use just the date
            return dt.replace(hour=0, minute=0, second=0, microsecond=0)\
                .strftime("%Y%m%d")
        # Partial day bucket
        bucket_hour = (dt.hour // hours) * hours
        return dt.replace(hour=bucket_hour, minute=0, second=0, microsecond=0)\
            .strftime("%Y%m%d%H%M")
    
    # Day buckets
    if window.endswith("d"):
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)\
            .strftime("%Y%m%d")
    
    # Default: minute precision
    return dt.strftime("%Y%m%d%H%M")


def create_correlation_id(
    rule_id: str,
    window: str = "24h",
    timestamp: Optional[datetime] = None,
    keys: Optional[List[Any]] = None,
) -> str:
    """Create a stable correlation ID for event deduplication.
    
    Generates a deterministic identifier for grouping related alerts,
    enabling deduplication and correlation across systems. The ID is
    stable within the specified time window.
    
    Example:
        # All alerts from same user to same IP in same hour
        # get the same correlation ID:
        id1 = create_correlation_id(
            "auth-failure",
            window="1h",
            keys=["192.168.1.100", "alice"]
        )
        id2 = create_correlation_id(
            "auth-failure", 
            window="1h",
            keys=["alice", "192.168.1.100"]  # Note: order independent
        )
        assert id1 == id2  # Order-independent grouping
    
    Args:
        rule_id: Detection rule or signature ID
        window: Time window for grouping ("24h", "1h", "5m", etc.)
        timestamp: Event timestamp (defaults to now)
        keys: Additional correlation factors (order-independent)
        
    Returns:
        Stable correlation ID (format: corr-<16 hex chars>)
    """
    # Build canonical key
    key_parts = [
        str(rule_id),
        bucket_timestamp(timestamp or datetime.now(timezone.utc), window),
    ]
    
    # Add sorted correlation keys for order-independence
    if keys:
        sorted_keys = sorted(str(k) for k in keys if k)
        key_parts.extend(sorted_keys)
    
    canonical_key = "|".join(key_parts)
    
    # Hash to stable short identifier
    digest = hashlib.sha256(canonical_key.encode("utf-8")).hexdigest()[:16]
    return f"corr-{digest}"


# ============================================================================
# Secret Redaction — Automatic Sanitization of Sensitive Values
# ============================================================================

# Patterns that trigger automatic redaction
_SENSITIVE_PATTERNS = {
    "password", "passwd", "pwd", "pin",
    "secret", "token", "auth", "bearer",
    "api_key", "apikey", "key", "private_key",
    "access_token", "refresh_token",
    "credential", "credentials",
    "session_id", "sessionid", "cookie",
    "aws_", "gcp_", "azure_", "stripe_",
}


def is_sensitive_key(key: str) -> bool:
    """Check if a key name suggests sensitive content."""
    key_lower = str(key).lower()
    return any(pattern in key_lower for pattern in _SENSITIVE_PATTERNS)


def redact_value(value: Any, max_depth: int = 10) -> Any:
    """Recursively redact sensitive values from data.
    
    Automatically masks values for keys matching sensitivity patterns.
    Preserves structure (dict/list/tuple) and non-sensitive values.
    Protects against circular references with max_depth limit.
    
    Args:
        value: Object to redact (dict, list, tuple, scalar, etc.)
        max_depth: Maximum recursion depth (prevents infinite loops)
        
    Returns:
        Redacted copy (non-mutating)
    """
    return _redact_recursive(value, 0, max_depth)


def _redact_recursive(value: Any, depth: int, max_depth: int) -> Any:
    """Recursive redaction helper."""
    if depth > max_depth:
        return value
    
    if isinstance(value, dict):
        return {
            k: (
                "***" if is_sensitive_key(k)
                else _redact_recursive(v, depth + 1, max_depth)
            )
            for k, v in value.items()
        }
    
    if isinstance(value, (list, tuple)):
        redacted = [_redact_recursive(v, depth + 1, max_depth) for v in value]
        return type(value)(redacted)
    
    return value


def redact_in_place(data: Dict[str, Any]) -> None:
    """Redact sensitive values in a dict (mutates in place).
    
    Faster than redact_value() for large dicts, but modifies the
    original. Useful for sanitizing API responses before logging.
    
    Args:
        data: Dictionary to redact (modified in place)
    """
    for key in list(data.keys()):
        if is_sensitive_key(key):
            data[key] = "***"
        elif isinstance(data[key], dict):
            redact_in_place(data[key])


def sanitized_json(obj: Any, indent: int = 2) -> str:
    """Serialize to JSON with automatic secret redaction.
    
    Single-step function for safe logging: redacts then serializes.
    Ensures secrets never leak into logs or stdout.
    
    Args:
        obj: Object to serialize
        indent: Indentation level (2 for readable, None for compact)
        
    Returns:
        Sanitized JSON string
    """
    redacted = redact_value(obj)
    return json.dumps(redacted, indent=indent, default=str)
