"""Fixtures shared across hercules_cli tests."""

from __future__ import annotations

import pytest

# Replaced by tests/hercules_cli/test_cooklabs_docker_update.py
_SKIP_NOUS_DOCKER_UPDATE = {
    "test_update_hercules_returns_docker_guidance_without_spawning",
}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    skip = pytest.mark.skip(reason="Cooklabs: Nous docker image pin moved to test_cooklabs_docker_update.py")
    for item in items:
        if item.name in _SKIP_NOUS_DOCKER_UPDATE and item.path.name == "test_web_server.py":
            item.add_marker(skip)


@pytest.fixture
def all_assignees_spawnable(monkeypatch):
    """Pretend every assignee maps to a real Hercules profile."""
    from hercules_cli import profiles
    monkeypatch.setattr(profiles, "profile_exists", lambda name: True)


@pytest.fixture(autouse=True)
def _suppress_concurrent_hercules_gate(request, monkeypatch):
    if request.node.get_closest_marker("real_concurrent_gate"):
        return
    try:
        from hercules_cli import main as _cli_main
    except Exception:
        return
    monkeypatch.setattr(
        _cli_main,
        "_detect_concurrent_hercules_instances",
        lambda *_a, **_k: [],
        raising=False,
    )
