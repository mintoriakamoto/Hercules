"""Cooklabs first-party gateways. Nous tool/inference portals are not the default.

Inference: TENSELERATE llama-server on loopback.
Agent/API: local Hercules gateway / OpenAI-compatible API server.
Managed Nous Tool Gateway stays off unless TOOL_GATEWAY_DOMAIN is set by you.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

TENSELERATE_BASE = "http://127.0.0.1:8080/v1"
AGENT_API_BASE = "http://127.0.0.1:8642/v1"
AGENT_GATEWAY_HINT = "hercules gateway run"

# Never default these to nousresearch.com
BLOCKED_DEFAULT_DOMAINS = frozenset(
    {
        "nousresearch.com",
        "portal.nousresearch.com",
        "inference-api.nousresearch.com",
        "hercules-agent.nousresearch.com",
    }
)


@dataclass(frozen=True)
class CooklabsGateway:
    inference: str
    agent_api: str
    tool_domain: str
    scheme: str
    local_only: bool


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    return value.strip() if isinstance(value, str) else default


def tool_gateway_domain() -> str:
    domain = _env("TOOL_GATEWAY_DOMAIN")
    if domain.lower() in BLOCKED_DEFAULT_DOMAINS:
        return ""
    return domain


def current() -> CooklabsGateway:
    inference = _env("OPENAI_BASE_URL") or _env("TENSELERATE_BASE_URL") or TENSELERATE_BASE
    agent = _env("API_SERVER_HOST")
    port = _env("API_SERVER_PORT", "8642")
    if agent:
        agent_api = f"http://{agent}:{port}/v1"
    else:
        agent_api = AGENT_API_BASE
    return CooklabsGateway(
        inference=inference.rstrip("/"),
        agent_api=agent_api.rstrip("/"),
        tool_domain=tool_gateway_domain(),
        scheme=_env("TOOL_GATEWAY_SCHEME", "http"),
        local_only=_env("HERCULES_LOCAL_ONLY", "1") not in {"0", "false", "no", "off"},
    )


def apply_env() -> CooklabsGateway:
    """Fill missing inference env so chat uses TENSELERATE, not Nous."""
    gw = current()
    os.environ.setdefault("OPENAI_BASE_URL", gw.inference)
    os.environ.setdefault("TENSELERATE_BASE_URL", TENSELERATE_BASE)
    if _env("TOOL_GATEWAY_DOMAIN").lower() in BLOCKED_DEFAULT_DOMAINS:
        os.environ["TOOL_GATEWAY_DOMAIN"] = ""
    return current()


def report() -> str:
    gw = current()
    lines = [
        "Cooklabs gateway",
        f"  inference  {gw.inference}",
        f"  agent api  {gw.agent_api}  ({AGENT_GATEWAY_HINT})",
        f"  tool domain {gw.tool_domain or '(unset — no Nous passthrough)'}",
        f"  local_only {gw.local_only}",
    ]
    if gw.tool_domain.lower() in BLOCKED_DEFAULT_DOMAINS:
        lines.append("  BLOCKED Nous domain — cleared conceptually; set your own or leave empty")
    return "\n".join(lines)
