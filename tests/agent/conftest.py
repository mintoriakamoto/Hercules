"""Test fixtures for agent tests."""

import pytest
from unittest.mock import patch, MagicMock


def _clear_model_metadata_caches():
    """Clear all model metadata caches (in-memory and on-disk)."""
    import agent.model_metadata as mm

    # Clear in-memory caches - set to their initial values
    mm._model_metadata_cache = {}
    mm._model_metadata_cache_time = 0
    mm._novita_metadata_cache = {}
    mm._novita_metadata_cache_time = 0
    mm._endpoint_model_metadata_cache = {}
    mm._endpoint_model_metadata_cache_time = {}
    mm._endpoint_probe_path_cache = {}
    mm._codex_oauth_context_cache = {}
    mm._codex_oauth_context_cache_time = 0.0

    # Also clear any context length caches that might be populated
    # This is important because models.dev results and other probes might cache data
    try:
        # Reset the local context cache if it exists
        if hasattr(mm, '_local_context_cache'):
            mm._local_context_cache = {}
    except:
        pass

    # Remove disk cache files (multiple attempts to handle edge cases)
    for _ in range(3):  # Retry up to 3 times
        try:
            cache_file = mm._get_model_metadata_cache_path()
            if cache_file.exists():
                cache_file.unlink()
                break
        except Exception:
            pass

    for _ in range(3):  # Retry up to 3 times
        try:
            context_cache_file = mm._get_context_cache_path()
            if context_cache_file.exists():
                context_cache_file.unlink()
                break
        except Exception:
            pass


@pytest.fixture(autouse=True)
def clear_model_metadata_caches_and_mock_requests(monkeypatch, _hermetic_environment):
    """Clear model metadata caches for all tests.

    Depends on _hermetic_environment fixture which already isolates HERCULES_HOME.
    We create the cache directory and clear in-memory caches before and after tests.
    """
    from pathlib import Path
    from hercules_constants import get_hercules_home

    # Ensure cache directory exists (created by _hermetic_environment fixture)
    hercules_home = get_hercules_home()
    cache_dir = hercules_home / "cache"
    if not cache_dir.exists():
        cache_dir.mkdir(parents=True, exist_ok=True)

    # Clear before test
    _clear_model_metadata_caches()

    yield

    # Clear after test as well
    _clear_model_metadata_caches()
