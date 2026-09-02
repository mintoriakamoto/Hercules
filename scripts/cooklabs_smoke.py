#!/usr/bin/env python3
"""Offline + optional live smoke for the Cooklabs TENSELERATE provider.

Usage (from repo root):
    python3 scripts/cooklabs_smoke.py

Exit codes:
    0  plugin registered; live /v1/models optional
    1  plugin missing / import broken
    2  plugin ok, llama-server not reachable (expected if GPU box is off)
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    print("== Cooklabs smoke ==")
    yaml_path = ROOT / "cli-config.cooklabs.yaml"
    if not yaml_path.is_file():
        print("FAIL: cli-config.cooklabs.yaml missing")
        return 1
    text = yaml_path.read_text()
    for needle in ("provider: tenselerate", "read:", "coder:", "developer:"):
        if needle not in text:
            print(f"FAIL: {needle!r} not in cli-config.cooklabs.yaml")
            return 1
    print("config overlay: PASS")

    plugin = ROOT / "plugins" / "model-providers" / "tenselerate" / "__init__.py"
    if not plugin.is_file():
        print("FAIL: tenselerate plugin missing")
        return 1
    print("plugin file: PASS")

    try:
        from providers import get_provider_profile, list_providers
    except Exception as exc:
        print(f"FAIL: cannot import providers: {exc}")
        return 1

    profile = get_provider_profile("tenselerate")
    if profile is None:
        names = sorted(p.name for p in list_providers())
        print(f"FAIL: tenselerate not registered. have={names[-8:]}")
        return 1
    print(f"registry: PASS name={profile.name} base_url={profile.base_url}")

    alias = get_provider_profile("svmi")
    if alias is None or alias.name != "tenselerate":
        print("FAIL: alias svmi did not resolve to tenselerate")
        return 1
    print("alias svmi: PASS")

    url = (profile.models_url or profile.base_url.rstrip("/") + "/models").strip()
    print(f"probe {url}")
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=2) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        print(f"llama-server: PASS http={resp.status} body={body[:200]!r}")
        return 0
    except Exception as exc:
        print(f"llama-server: DOWN ({exc.__class__.__name__}: {exc})")
        print("plugin is wired; start TENSELERATE llama-server on :8080 and re-run")
        return 2


if __name__ == "__main__":
    sys.exit(main())
