"""Auxiliary providers must honor providers.local_only (no cloud fallback).

The main provider path enforces local-only at resolve_runtime_provider, but
auxiliary tasks (compression, memory, titles, session search, vision) resolve
their own clients. In local-only mode a non-local auxiliary endpoint must be
treated as unavailable so nothing silently reaches cloud.
"""

from types import SimpleNamespace
from unittest.mock import patch

import agent.auxiliary_client as ac

CLOUD = "https://openrouter.ai/api/v1"
LOCAL = "http://localhost:11434/v1"


def _client(base_url):
    return SimpleNamespace(base_url=base_url, close=lambda: None)


def _patch_mode(enabled):
    return patch(
        "hercules_cli.runtime_provider.local_only_mode_enabled", return_value=enabled
    )


def test_helper_none_client_is_not_blocked():
    with _patch_mode(True):
        assert ac._aux_endpoint_blocked_by_local_only(None) is False


def test_helper_blocks_cloud_only_when_mode_on():
    with _patch_mode(False):
        assert ac._aux_endpoint_blocked_by_local_only(_client(CLOUD)) is False
    with _patch_mode(True):
        assert ac._aux_endpoint_blocked_by_local_only(_client(CLOUD)) is True


def test_helper_allows_local_endpoint_under_mode():
    with _patch_mode(True):
        assert ac._aux_endpoint_blocked_by_local_only(_client(LOCAL)) is False


def test_wrapper_passes_cloud_through_when_mode_off():
    cloud = _client(CLOUD)
    with patch.object(
        ac, "_resolve_provider_client_impl", return_value=(cloud, "m")
    ), _patch_mode(False):
        client, model = ac.resolve_provider_client("openrouter")
    assert client is cloud
    assert model == "m"


def test_wrapper_blocks_cloud_when_mode_on():
    cloud = _client(CLOUD)
    with patch.object(
        ac, "_resolve_provider_client_impl", return_value=(cloud, "m")
    ), _patch_mode(True):
        client, model = ac.resolve_provider_client("openrouter")
    assert client is None
    assert model is None


def test_wrapper_allows_local_when_mode_on():
    local = _client(LOCAL)
    with patch.object(
        ac, "_resolve_provider_client_impl", return_value=(local, "m")
    ), _patch_mode(True):
        client, model = ac.resolve_provider_client("custom")
    assert client is local
    assert model == "m"


def test_wrapper_closes_the_blocked_client():
    closed = {"v": False}

    def _close():
        closed["v"] = True

    cloud = SimpleNamespace(base_url=CLOUD, close=_close)
    with patch.object(
        ac, "_resolve_provider_client_impl", return_value=(cloud, "m")
    ), _patch_mode(True):
        ac.resolve_provider_client("openrouter")
    assert closed["v"] is True
