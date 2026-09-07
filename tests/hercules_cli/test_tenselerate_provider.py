"""Cooklabs TENSELERATE provider is discoverable without a live server."""

from providers import get_provider_profile


def test_tenselerate_registered():
    profile = get_provider_profile("tenselerate")
    assert profile is not None
    assert profile.name == "tenselerate"
    assert profile.base_url.startswith("http://127.0.0.1:8080")
    assert profile.supports_health_check is True


def test_tenselerate_aliases():
    for alias in ("svmi", "llama-server", "tenselerate-local"):
        profile = get_provider_profile(alias)
        assert profile is not None, alias
        assert profile.name == "tenselerate"
