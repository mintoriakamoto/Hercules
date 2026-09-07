from hercules_cli.cooklabs_gateway import (
    BLOCKED_DEFAULT_DOMAINS,
    TENSELERATE_BASE,
    apply_env,
    current,
    tool_gateway_domain,
)


def test_nous_domains_blocked(monkeypatch):
    monkeypatch.setenv("TOOL_GATEWAY_DOMAIN", "nousresearch.com")
    assert tool_gateway_domain() == ""
    assert "nousresearch.com" in BLOCKED_DEFAULT_DOMAINS


def test_default_inference_is_tenselerate(monkeypatch):
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("TENSELERATE_BASE_URL", raising=False)
    assert current().inference == TENSELERATE_BASE.rstrip("/")


def test_apply_clears_nous_tool_domain(monkeypatch):
    monkeypatch.setenv("TOOL_GATEWAY_DOMAIN", "portal.nousresearch.com")
    gw = apply_env()
    assert gw.tool_domain == ""
