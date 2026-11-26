"""Tests for SSRF protection in url_safety module."""

import socket
from unittest.mock import patch

from tools.url_safety import (
    is_safe_url,
    async_is_safe_url,
    is_always_blocked_url,
    normalize_url_for_request,
    redirect_target_from_response,
    _is_blocked_ip,
    _global_allow_private_urls,
    _reset_allow_private_cache,
)

import ipaddress
import pytest


class TestNormalizeUrlForRequest:
    def test_percent_encodes_non_ascii_path(self):
        assert (
            normalize_url_for_request("https://wttr.in/Köln")
            == "https://wttr.in/K%C3%B6ln"
        )

    def test_preserves_existing_percent_escapes(self):
        assert (
            normalize_url_for_request("https://wttr.in/K%C3%B6ln")
            == "https://wttr.in/K%C3%B6ln"
        )

    def test_preserves_reserved_query_syntax(self):
        assert (
            normalize_url_for_request("https://example.com/search?q=Köln&lang=de")
            == "https://example.com/search?q=K%C3%B6ln&lang=de"
        )

    def test_idna_encodes_hostname(self):
        assert (
            normalize_url_for_request("https://münich.example/Köln")
            == "https://xn--mnich-kva.example/K%C3%B6ln"
        )

    def test_repairs_space_between_scheme_and_authority(self):
        assert (
            normalize_url_for_request("https:// docs.openclaw.ai")
            == "https://docs.openclaw.ai"
        )

    def test_repairs_tab_between_scheme_and_authority(self):
        assert (
            normalize_url_for_request("https://	docs.openclaw.ai/path")
            == "https://docs.openclaw.ai/path"
        )

    def test_trims_but_preserves_path_and_query_space_semantics(self):
        assert (
            normalize_url_for_request(" https://example.com/a b?q=c d ")
            == "https://example.com/a%20b?q=c%20d"
        )

    def test_does_not_collapse_embedded_scheme_separator_in_query(self):
        assert (
            normalize_url_for_request(
                "https://example.com/r?next=https:// evil.example"
            )
            == "https://example.com/r?next=https://%20evil.example"
        )




class _FakeResponse:
    """Minimal stand-in for an httpx response as seen inside a response hook."""

    def __init__(self, *, is_redirect, location=None, url="", next_request=None):
        self.is_redirect = is_redirect
        self.headers = {"location": location} if location else {}
        self.url = url
        self.next_request = next_request


class _FakeNextRequest:
    def __init__(self, url):
        self.url = url


class TestRedirectTargetFromResponse:
    """redirect_target_from_response is the SSRF-guard boundary for httpx hooks.

    Inside httpx AsyncClient response hooks, ``response.next_request`` is often
    ``None`` even for a real redirect, so a guard keyed only on it silently
    never fires. Resolving from the ``Location`` header closes that hole.
    """

    def test_absolute_location_without_next_request(self):
        # The exact bypass: redirect present, next_request unset, private target.
        resp = _FakeResponse(
            is_redirect=True,
            location="http://169.254.169.254/latest/meta-data",
            url="https://public.example/image.png",
        )
        assert (
            redirect_target_from_response(resp)
            == "http://169.254.169.254/latest/meta-data"
        )

    def test_relative_location_is_resolved_against_response_url(self):
        resp = _FakeResponse(
            is_redirect=True,
            location="/redir",
            url="https://public.example/image.png",
        )
        assert redirect_target_from_response(resp) == "https://public.example/redir"

    def test_non_redirect_returns_none(self):
        resp = _FakeResponse(is_redirect=False, location="http://169.254.169.254/")
        assert redirect_target_from_response(resp) is None

    def test_falls_back_to_next_request_when_no_location(self):
        resp = _FakeResponse(
            is_redirect=True,
            next_request=_FakeNextRequest("http://10.0.0.1/meta"),
        )
        assert redirect_target_from_response(resp) == "http://10.0.0.1/meta"

    def test_no_location_no_next_request_returns_none(self):
        resp = _FakeResponse(is_redirect=True)
        assert redirect_target_from_response(resp) is None
