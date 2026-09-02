"""Cooklabs first-party gateway endpoints.

Nous Tool Gateway entitlement is gone. Cooklabs traffic stays on this machine:

- Control / messaging gateway: hercules gateway  → http://127.0.0.1:8645
- Inference: TENSELERATE llama-server           → http://127.0.0.1:8080/v1

Do not set TOOL_GATEWAY_DOMAIN=nousresearch.com.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

CONTROL_GATEWAY = os.environ.get("COOKLABS_GATEWAY_URL", "http://127.0.0.1:8645").rstrip("/")
INFERENCE_GATEWAY = os.environ.get("COOKLABS_INFERENCE_URL", "http://127.0.0.1:8080/v1").rstrip("/")


def apply_env() -> None:
    """Fill empty Cooklabs env so we never inherit a Nous domain."""
    os.environ.setdefault("COOKLABS_GATEWAY_URL", CONTROL_GATEWAY)
    os.environ.setdefault("COOKLABS_INFERENCE_URL", INFERENCE_GATEWAY)
    domain = os.environ.get("TOOL_GATEWAY_DOMAIN", "").strip().lower()
    if domain in {"nousresearch.com", "portal.nousresearch.com"}:
        os.environ.pop("TOOL_GATEWAY_DOMAIN", None)


def _probe(url: str, timeout: float = 2.0) -> dict[str, Any]:
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()[:400].decode("utf-8", errors="replace")
            return {"url": url, "ok": True, "status": getattr(resp, "status", 200), "body": body}
    except Exception as exc:
        return {"url": url, "ok": False, "error": f"{exc.__class__.__name__}: {exc}"}


def status() -> dict[str, Any]:
    apply_env()
    return {
        "owner": "cooklabs",
        "nous_tool_gateway": False,
        "control": {"url": CONTROL_GATEWAY, **_probe(CONTROL_GATEWAY + "/")},
        "inference": {
            "url": INFERENCE_GATEWAY,
            **_probe(INFERENCE_GATEWAY + "/models"),
        },
        "start": {
            "control": "hercules gateway",
            "inference": "bash TENSELERATE-/scripts/cooklabs_serve.sh MODEL.gguf 3060",
        },
    }


def format_status(data: dict[str, Any] | None = None) -> str:
    data = data or status()
    lines = [
        "Cooklabs gateway (not Nous)",
        f"  control   {data['control']['url']}  {'UP' if data['control'].get('ok') else 'DOWN'}",
        f"  inference {data['inference']['url']}  {'UP' if data['inference'].get('ok') else 'DOWN'}",
        f"  start control:   {data['start']['control']}",
        f"  start inference: {data['start']['inference']}",
    ]
    return "\n".join(lines)


def main() -> int:
    import sys

    data = status()
    if sys.argv[1:] == ["--json"]:
        print(json.dumps(data, indent=2))
        return 0
    print(format_status(data))
    return 0 if data["control"].get("ok") or data["inference"].get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
