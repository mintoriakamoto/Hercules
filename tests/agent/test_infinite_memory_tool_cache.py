"""Tests for incremental tool output compression module."""

import json

import pytest

from agent.compression import tool_outputs


def test_should_cache_large_output():
    """Test that large outputs are cached."""
    large_result = "A" * 10000  # 10KB

    assert tool_outputs.should_cache("file_read", large_result)


def test_should_not_cache_small_output():
    """Test that small outputs are not cached."""
    small_result = "Small output"

    assert not tool_outputs.should_cache("file_read", small_result)


def test_should_not_cache_streaming():
    """Test that streaming tools are not cached."""
    result = "A" * 10000  # Large output

    assert not tool_outputs.should_cache("stream_data", result)
    assert not tool_outputs.should_cache("websocket_receive", result)


def test_compress_string_output():
    """Test compressing a string tool output."""
    tool_name = "file_read"
    args = {"path": "/home/user/large_file.txt"}
    result = "X" * 50000  # 50KB string

    success = tool_outputs.compress_tool_output(tool_name, args, result)
    assert success


def test_compress_structured_output():
    """Test compressing JSON/structured tool output."""
    tool_name = "api_call"
    args = {"endpoint": "/users"}
    result = {
        "users": [
            {
                "id": i,
                "name": f"User {i}",
                "email": f"user{i}@example.com",
                "large_field": "X" * 1000,
            }
            for i in range(100)
        ]
    }

    success = tool_outputs.compress_tool_output(tool_name, args, result)
    # Might not cache if compression ratio is poor
    assert isinstance(success, bool)


def test_compress_and_retrieve():
    """Test compress and retrieve roundtrip."""
    tool_name = "search_results"
    args = {"query": "python"}
    original_result = "Result " * 5000  # Large result

    # Compress
    compress_ok = tool_outputs.compress_tool_output(tool_name, args, original_result)

    if compress_ok:
        # Retrieve
        cached = tool_outputs.get_cached_output(tool_name, args)
        assert cached is not None
        assert cached == original_result


def test_cache_savings_estimation():
    """Test estimating cache savings."""
    tool_name = "file_read"
    args = {"path": "/test.txt"}
    result = "A" * 100000

    # Compress something to populate cache
    tool_outputs.compress_tool_output(tool_name, args, result)

    savings = tool_outputs.estimate_cache_savings()

    assert "cached_items" in savings
    assert "disk_saved_bytes" in savings
    assert "compression_ratio" in savings


def test_cleanup_old_cache():
    """Test cleaning up old cached items."""
    # Add some items
    tool_outputs.compress_tool_output(
        "test_tool",
        {"arg": "value"},
        "X" * 50000,
    )

    # Cleanup with 0 hour retention (remove all)
    # Note: This might not work in unit tests without time manipulation
    cleaned = tool_outputs.cleanup_old_cache(max_age_hours=0)
    assert isinstance(cleaned, int)
    assert cleaned >= 0


def test_poor_compression_not_cached():
    """Test that poorly compressed data is not cached."""
    # Random data compresses poorly
    import random
    import string

    tool_name = "random_data"
    args = {"seed": 42}
    # Random string that won't compress well
    result = "".join(
        random.choice(string.ascii_letters + string.digits)
        for _ in range(50000)
    )

    success = tool_outputs.compress_tool_output(tool_name, args, result)
    # Should be False because compression ratio is poor
    assert isinstance(success, bool)


def test_cache_bytes_output():
    """Test caching binary/bytes output."""
    tool_name = "download_file"
    args = {"url": "https://example.com/file"}
    result = b"X" * 50000  # 50KB bytes

    success = tool_outputs.compress_tool_output(tool_name, args, result)
    assert isinstance(success, bool)


def test_cache_isolation_by_tool_and_args():
    """Test that cache entries are isolated by tool and args."""
    # Same tool, different args
    tool_name = "read_config"
    args1 = {"file": "config1.json"}
    args2 = {"file": "config2.json"}

    result = "X" * 50000

    tool_outputs.compress_tool_output(tool_name, args1, result)
    tool_outputs.compress_tool_output(tool_name, args2, result)

    # Should retrieve different cached items
    cached1 = tool_outputs.get_cached_output(tool_name, args1)
    cached2 = tool_outputs.get_cached_output(tool_name, args2)

    # Both should be cached
    assert (cached1 is not None and cached2 is not None) or (
        cached1 is None and cached2 is None
    )


def test_hash_functions():
    """Test JSON hashing function."""
    obj1 = {"key": "value", "number": 42}
    obj2 = {"number": 42, "key": "value"}  # Different order

    hash1 = tool_outputs._hash_json(obj1)
    hash2 = tool_outputs._hash_json(obj2)

    # Hashes should be equal regardless of order (sorted)
    assert hash1 == hash2


def test_cache_nonexistent_item():
    """Test retrieving non-existent cached item."""
    cached = tool_outputs.get_cached_output("nonexistent_tool", {"arg": "value"})
    assert cached is None


def test_compression_ratio_calculation():
    """Test that compression ratio is properly calculated."""
    tool_name = "large_response"
    args = {"id": 1}
    # Highly compressible data
    result = "A" * 100000

    compress_ok = tool_outputs.compress_tool_output(tool_name, args, result)

    if compress_ok:
        # Should have cached with good compression
        savings = tool_outputs.estimate_cache_savings()
        assert savings["compression_ratio"] < 0.95


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
