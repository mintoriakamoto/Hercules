"""Test fixtures for agent tests."""

import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def clear_model_metadata_caches_and_mock_requests():
    """Clear model metadata caches and mock network requests for all tests."""
    import agent.model_metadata as mm

    # Clear before test
    mm._model_metadata_cache = {}
    mm._model_metadata_cache_time = 0
    mm._novita_metadata_cache = {}
    mm._novita_metadata_cache_time = 0
    mm._endpoint_model_metadata_cache = {}
    mm._endpoint_model_metadata_cache_time = {}
    mm._endpoint_probe_path_cache = {}
    mm._codex_oauth_context_cache = {}
    mm._codex_oauth_context_cache_time = 0.0

    # Remove disk cache
    try:
        cache_file = mm._get_model_metadata_cache_path()
        if cache_file.exists():
            cache_file.unlink()
    except Exception:
        pass

    # Remove context length cache
    try:
        context_cache_file = mm._get_context_cache_path()
        if context_cache_file.exists():
            context_cache_file.unlink()
    except Exception:
        pass

    yield

    # Clear after test as well
    mm._model_metadata_cache = {}
    mm._model_metadata_cache_time = 0
    mm._novita_metadata_cache = {}
    mm._novita_metadata_cache_time = 0
    mm._endpoint_model_metadata_cache = {}
    mm._endpoint_model_metadata_cache_time = {}
    mm._endpoint_probe_path_cache = {}
    mm._codex_oauth_context_cache = {}
    mm._codex_oauth_context_cache_time = 0.0

    # Remove disk cache again
    try:
        cache_file = mm._get_model_metadata_cache_path()
        if cache_file.exists():
            cache_file.unlink()
    except Exception:
        pass

    # Remove context length cache again
    try:
        context_cache_file = mm._get_context_cache_path()
        if context_cache_file.exists():
            context_cache_file.unlink()
    except Exception:
        pass
