from hercules_cli.cooklabs_gateway import CONTROL_GATEWAY, INFERENCE_GATEWAY, apply_env, format_status, status


def test_defaults_are_loopback_not_nous():
    assert CONTROL_GATEWAY.startswith("http://127.0.0.1")
    assert ":8645" in CONTROL_GATEWAY
    assert INFERENCE_GATEWAY.startswith("http://127.0.0.1")
    assert "8080" in INFERENCE_GATEWAY
    assert "nousresearch" not in CONTROL_GATEWAY
    assert "nousresearch" not in INFERENCE_GATEWAY


def test_apply_env_strips_nous_domain(monkeypatch):
    monkeypatch.setenv("TOOL_GATEWAY_DOMAIN", "nousresearch.com")
    apply_env()
    import os

    assert os.environ.get("TOOL_GATEWAY_DOMAIN", "") != "nousresearch.com"


def test_status_shape():
    data = status()
    assert data["owner"] == "cooklabs"
    assert data["nous_tool_gateway"] is False
    text = format_status(data)
    assert "not Nous" in text
