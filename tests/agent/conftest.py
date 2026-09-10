"""Test fixtures for agent tests."""

import pytest
from unittest.mock import patch, MagicMock
import importlib
import sys


def _clear_model_metadata_caches():
    """Clear all model metadata caches (in-memory and on-disk)."""
    import agent.model_metadata as mm

    # Clear in-memory caches by directly mutating the dict/cache objects
    # This ensures that any code holding references to these objects sees the changes
    try:
        mm._model_metadata_cache.clear()
        mm._model_metadata_cache_time = 0
    except (AttributeError, TypeError):
        mm._model_metadata_cache = {}
        mm._model_metadata_cache_time = 0

    try:
        mm._novita_metadata_cache.clear()
        mm._novita_metadata_cache_time = 0
    except (AttributeError, TypeError):
        mm._novita_metadata_cache = {}
        mm._novita_metadata_cache_time = 0

    try:
        mm._endpoint_model_metadata_cache.clear()
    except (AttributeError, TypeError):
        mm._endpoint_model_metadata_cache = {}

    try:
        mm._endpoint_model_metadata_cache_time.clear()
    except (AttributeError, TypeError):
        mm._endpoint_model_metadata_cache_time = {}

    try:
        mm._endpoint_probe_path_cache.clear()
    except (AttributeError, TypeError):
        mm._endpoint_probe_path_cache = {}

    try:
        mm._codex_oauth_context_cache.clear()
        mm._codex_oauth_context_cache_time = 0.0
    except (AttributeError, TypeError):
        mm._codex_oauth_context_cache = {}
        mm._codex_oauth_context_cache_time = 0.0

    # Also clear any context length caches that might be populated
    try:
        if hasattr(mm, '_local_context_cache'):
            mm._local_context_cache.clear()
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
    """Clear all module-level caches for all tests to prevent cross-test pollution.

    Depends on _hermetic_environment fixture which already isolates HERCULES_HOME.
    Uses monkeypatch to directly clear cache objects in all agent modules,
    ensuring fresh state for each test regardless of how functions are imported.
    """
    from pathlib import Path
    from hercules_constants import get_hercules_home
    import agent.model_metadata as mm

    # CRITICAL: Force import all agent modules to ensure they're loaded before we clear caches.
    # This prevents a scenario where a test is the first to import a module, getting fresh
    # (but polluted) caches created at import time before this fixture runs.
    try:
        import agent.bedrock_adapter
        import agent.anthropic_adapter
        import agent.i18n
        import agent.lsp.workspace
        import agent.auxiliary_client
        import agent.vertex_adapter
        import agent.skill_bundles
        import agent.models_dev
        import agent.pet.manifest
    except Exception:
        pass

    # Ensure cache directory exists (created by _hermetic_environment fixture)
    hercules_home = get_hercules_home()
    cache_dir = hercules_home / "cache"
    if not cache_dir.exists():
        cache_dir.mkdir(parents=True, exist_ok=True)

    # Remove disk cache files first
    for _ in range(3):
        try:
            cache_file = mm._get_model_metadata_cache_path()
            if cache_file.exists():
                cache_file.unlink()
            break
        except Exception:
            pass

    for _ in range(3):
        try:
            context_cache_file = mm._get_context_cache_path()
            if context_cache_file.exists():
                context_cache_file.unlink()
            break
        except Exception:
            pass

    # Clear model_metadata module caches
    monkeypatch.setattr(mm, "_model_metadata_cache", {})
    monkeypatch.setattr(mm, "_model_metadata_cache_time", 0)
    monkeypatch.setattr(mm, "_novita_metadata_cache", {})
    monkeypatch.setattr(mm, "_novita_metadata_cache_time", 0)
    monkeypatch.setattr(mm, "_endpoint_model_metadata_cache", {})
    monkeypatch.setattr(mm, "_endpoint_model_metadata_cache_time", {})
    monkeypatch.setattr(mm, "_endpoint_probe_path_cache", {})
    monkeypatch.setattr(mm, "_codex_oauth_context_cache", {})
    monkeypatch.setattr(mm, "_codex_oauth_context_cache_time", 0.0)
    if hasattr(mm, "_local_context_cache"):
        monkeypatch.setattr(mm, "_local_context_cache", {})

    # Clear caches in other agent modules to prevent cross-test pollution
    _clear_other_module_caches(monkeypatch)

    # Kill any lingering Codex subprocesses that might have been spawned by previous tests
    # and left in an invalid state
    try:
        import subprocess
        subprocess.run(["pkill", "-f", "codex.*app-server"], timeout=2, capture_output=True)
    except Exception:
        pass

    yield


def _clear_other_module_caches(monkeypatch):
    """Clear module-level caches in all other agent modules."""
    # bedrock_adapter caches
    try:
        import agent.bedrock_adapter as ba
        if hasattr(ba, '_bedrock_runtime_client_cache'):
            monkeypatch.setattr(ba, '_bedrock_runtime_client_cache', {})
        if hasattr(ba, '_bedrock_control_client_cache'):
            monkeypatch.setattr(ba, '_bedrock_control_client_cache', {})
        if hasattr(ba, '_discovery_cache'):
            monkeypatch.setattr(ba, '_discovery_cache', {})
    except Exception:
        pass

    # anthropic_adapter cache
    try:
        import agent.anthropic_adapter as aa
        if hasattr(aa, '_claude_code_version_cache'):
            monkeypatch.setattr(aa, '_claude_code_version_cache', None)
    except Exception:
        pass

    # i18n cache
    try:
        import agent.i18n as i18n
        if hasattr(i18n, '_catalog_cache'):
            monkeypatch.setattr(i18n, '_catalog_cache', {})
    except Exception:
        pass

    # lsp workspace cache
    try:
        import agent.lsp.workspace as ws
        if hasattr(ws, '_workspace_cache'):
            monkeypatch.setattr(ws, '_workspace_cache', {})
    except Exception:
        pass

    # auxiliary_client cache
    try:
        import agent.auxiliary_client as ac
        if hasattr(ac, '_client_cache'):
            monkeypatch.setattr(ac, '_client_cache', {})
    except Exception:
        pass

    # vertex_adapter cache
    try:
        import agent.vertex_adapter as va
        if hasattr(va, '_creds_cache'):
            monkeypatch.setattr(va, '_creds_cache', {})
    except Exception:
        pass

    # skill_bundles cache
    try:
        import agent.skill_bundles as sb
        if hasattr(sb, '_bundles_cache'):
            monkeypatch.setattr(sb, '_bundles_cache', {})
    except Exception:
        pass

    # models_dev cache
    try:
        import agent.models_dev as md
        if hasattr(md, '_models_dev_cache'):
            monkeypatch.setattr(md, '_models_dev_cache', {})
    except Exception:
        pass

    # pet manifest cache
    try:
        import agent.pet.manifest as pm
        if hasattr(pm, '_cache'):
            monkeypatch.setattr(pm, '_cache', None)
    except Exception:
        pass
