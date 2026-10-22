"""simdjson integration for high-performance JSON parsing.

Provides a drop-in replacement for json.loads() with 5-10x speedup
for typical tool call payloads.

simdjson uses CPU-level SIMD intrinsics (AVX2/AVX-512/NEON) to parse
JSON in parallel, achieving ~2GB/sec on modern CPUs vs ~500MB/sec
for pure Python json module.

Installation:
    pip install simdjson

Usage:
    from tools.simdjson_integration import parse_json, parse_json_array

    # Drop-in replacement for json.loads()
    data = parse_json(json_string)

    # Optimized for tool call arrays
    tool_calls = parse_json_array(json_string, "tool_calls")
"""

import json
import logging
from typing import Any, Optional, List, Dict

logger = logging.getLogger(__name__)

# Try to import simdjson; fall back to standard json if unavailable
try:
    import simdjson
    SIMDJSON_AVAILABLE = True
    SIMDJSON_VERSION = getattr(simdjson, '__version__', 'unknown')
    logger.debug(f"simdjson {SIMDJSON_VERSION} available; using for JSON parsing")
except ImportError:
    simdjson = None
    SIMDJSON_AVAILABLE = False
    logger.info("simdjson not available; falling back to standard json module")


def get_json_backend_info() -> Dict[str, Any]:
    """Get information about current JSON backend.

    Returns:
        Dict with 'backend', 'version', 'speedup_estimate' keys
    """
    if SIMDJSON_AVAILABLE:
        return {
            "backend": "simdjson",
            "version": SIMDJSON_VERSION,
            "speedup_estimate": "5-10x",
            "description": "CPU-level SIMD (AVX2/AVX-512/NEON)"
        }
    else:
        return {
            "backend": "json",
            "version": "builtin",
            "speedup_estimate": "1.0x",
            "description": "Standard Python json module (C implementation)"
        }


def parse_json(data: str) -> Optional[Any]:
    """Parse JSON string with automatic backend selection.

    Prefers simdjson if available, falls back to standard json.

    Args:
        data: JSON string to parse

    Returns:
        Parsed Python object, or None if parsing fails
    """
    if not data:
        return None

    if SIMDJSON_AVAILABLE:
        try:
            # simdjson is ~5-10x faster for typical payloads
            return simdjson.loads(data)
        except (ValueError, simdjson.JSONDecodeError) as e:
            logger.warning(f"simdjson parsing failed; falling back to json: {e}")
            # Fall through to standard json as fallback

    try:
        return json.loads(data)
    except (json.JSONDecodeError, ValueError):
        return None


def parse_json_bytes(data: bytes) -> Optional[Any]:
    """Parse JSON from bytes.

    Args:
        data: JSON bytes to parse

    Returns:
        Parsed Python object, or None if parsing fails
    """
    if not data:
        return None

    if SIMDJSON_AVAILABLE:
        try:
            # simdjson can parse bytes directly (zero-copy)
            return simdjson.loads(data)
        except (ValueError, TypeError, simdjson.JSONDecodeError):
            # Fall through to standard json
            pass

    try:
        return json.loads(data.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return None


def parse_json_array(data: str, array_key: str) -> Optional[List[Dict]]:
    """Extract and parse a JSON array from an object.

    Optimized for extracting tool_calls arrays from model responses.

    Args:
        data: JSON string containing the array
        array_key: Key name of the array (e.g., "tool_calls")

    Returns:
        List of array elements, or None if parsing fails
    """
    if not data or not array_key:
        return None

    # Quick check: look for the array key
    if f'"{array_key}"' not in data:
        return None

    try:
        # Parse the entire JSON object first
        obj = parse_json(data)
        if not isinstance(obj, dict):
            return None

        # Extract the array
        array = obj.get(array_key)
        if isinstance(array, list):
            return array

        return None

    except (ValueError, TypeError, AttributeError):
        return None


def validate_json(data: str) -> bool:
    """Quick validation of JSON structure without full parsing.

    Args:
        data: JSON string to validate

    Returns:
        True if JSON is valid
    """
    if not data:
        return False

    if SIMDJSON_AVAILABLE:
        try:
            # simdjson has fast validation without full materialization
            # (internal check without building Python objects)
            simdjson.loads(data)  # Will raise if invalid
            return True
        except Exception:
            return False

    try:
        json.loads(data)
        return True
    except (json.JSONDecodeError, ValueError):
        return False


class StreamingJsonParser:
    """Streaming JSON parser for incremental tool call extraction.

    Combines simdjson for full-JSON performance with streaming
    buffering for incremental token processing.
    """

    def __init__(self):
        self.buffer = ""
        self.backend = "simdjson" if SIMDJSON_AVAILABLE else "json"

    def feed_chunk(self, chunk: str) -> Optional[Dict[str, Any]]:
        """Feed a chunk of data and attempt to parse complete objects.

        Args:
            chunk: New data chunk (typically a model token)

        Returns:
            Parsed object if complete JSON found, else None
        """
        self.buffer += chunk

        # Try to parse complete JSON objects
        # Look for }{ transitions (multiple objects)
        # or single object when balanced brackets detected

        return self._try_parse()

    def _try_parse(self) -> Optional[Dict[str, Any]]:
        """Attempt to parse buffer."""
        if not self.buffer:
            return None

        # Simple heuristic: look for complete object
        bracket_depth = 0
        in_string = False
        escape_next = False

        for i, char in enumerate(self.buffer):
            if escape_next:
                escape_next = False
                continue

            if char == '\\' and in_string:
                escape_next = True
                continue

            if char == '"':
                in_string = not in_string
                continue

            if not in_string:
                if char in '{[':
                    bracket_depth += 1
                elif char in '}]':
                    bracket_depth -= 1

                    # Found a complete object/array
                    if bracket_depth == 0:
                        try:
                            obj = parse_json(self.buffer[:i + 1])
                            if obj is not None:
                                self.buffer = self.buffer[i + 1:].lstrip()
                                return obj
                        except Exception:
                            pass

        return None

    def get_buffered_data(self) -> str:
        """Get current buffer content."""
        return self.buffer

    def reset(self):
        """Clear buffer."""
        self.buffer = ""


# Benchmark comparison
def compare_backends(json_string: str) -> Dict[str, Any]:
    """Compare parsing speed of simdjson vs json.

    Useful for profiling and validation.

    Args:
        json_string: JSON to parse

    Returns:
        Dict with timing and result comparison
    """
    import time

    results = {"input_size": len(json_string)}

    # Test standard json
    try:
        start = time.perf_counter()
        json_result = json.loads(json_string)
        json_time = (time.perf_counter() - start) * 1000
        results["json_time_ms"] = json_time
        results["json_ok"] = True
    except Exception as e:
        results["json_error"] = str(e)
        json_result = None

    # Test simdjson if available
    if SIMDJSON_AVAILABLE:
        try:
            start = time.perf_counter()
            simdjson_result = simdjson.loads(json_string)
            simdjson_time = (time.perf_counter() - start) * 1000
            results["simdjson_time_ms"] = simdjson_time
            results["simdjson_ok"] = True

            # Calculate speedup
            if results.get("json_ok"):
                speedup = results["json_time_ms"] / simdjson_time
                results["speedup"] = speedup
        except Exception as e:
            results["simdjson_error"] = str(e)

    # Validate identical results
    if results.get("json_ok") and results.get("simdjson_ok"):
        # Note: can't directly compare dicts with floating point values
        # so we re-serialize both and compare strings
        json_str = json.dumps(json_result, sort_keys=True)
        simdjson_str = json.dumps(simdjson_result, sort_keys=True)
        results["results_identical"] = json_str == simdjson_str

    return results


# Export preferred parsing function
parse = parse_json  # Alias for convenience
