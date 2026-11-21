"""Credential writes go to .env; config.yaml keeps only a ${VAR} reference."""

import pytest

from hercules_cli import config_secret_refs as refs


def test_names_follow_conventions():
    assert refs.model_api_key_env() == "HERCULES_MODEL_API_KEY"
    assert refs.aux_api_key_env("vision") == "AUXILIARY_VISION_API_KEY"
    assert refs.aux_api_key_env("delegation") == "HERCULES_DELEGATION_API_KEY"
    assert refs.endpoint_api_key_env("http://localhost:8080/v1") == "HERCULES_CUSTOM_LOCALHOST_8080_API_KEY"
    assert refs.endpoint_api_key_env("") == "HERCULES_MODEL_API_KEY"


def test_path_routing_only_for_credential_paths():
    cfg = {}
    assert refs.config_path_api_key_env(["model", "api_key"], cfg) == "HERCULES_MODEL_API_KEY"
    assert refs.config_path_api_key_env(["model", "default"], cfg) is None
    assert refs.config_path_api_key_env(["custom_providers", "0", "api_key"],
                                        {"custom_providers": [{"name": "lab"}]}) == "HERCULES_CUSTOM_LAB_API_KEY"


def test_references_and_empty_values_pass_through(monkeypatch):
    stored = []
    monkeypatch.setattr(refs, "store_secret", lambda n, v: stored.append((n, v)) or "X")
    assert refs.secret_ref_for("HERCULES_MODEL_API_KEY", "${OTHER}") == "${OTHER}"
    assert refs.secret_ref_for("HERCULES_MODEL_API_KEY", "") == ""
    assert stored == []


def test_literal_secret_is_stored_and_replaced_by_reference(monkeypatch):
    saved = {}
    import hercules_cli.config as cfg_mod
    monkeypatch.setattr(cfg_mod, "save_env_value", lambda k, v: saved.update({k: v}))
    assert refs.config_set_secret_value("model.api_key", "sk-test-1", {}) == "${HERCULES_MODEL_API_KEY}"
    assert saved == {"HERCULES_MODEL_API_KEY": "sk-test-1"}


def test_non_credential_value_is_untouched():
    assert refs.config_set_secret_value("model.default", "gpt-4o", {}) == "gpt-4o"


def test_set_config_value_keeps_key_out_of_config_yaml(tmp_path, monkeypatch):
    monkeypatch.setenv("HERCULES_HOME", str(tmp_path))
    from hercules_cli import config as cfg_mod

    cfg_mod.set_config_value("model.api_key", "sk-test-42")

    yaml_text = (tmp_path / "config.yaml").read_text(encoding="utf-8")
    env_text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "sk-test-42" not in yaml_text
    assert "${HERCULES_MODEL_API_KEY}" in yaml_text
    assert "HERCULES_MODEL_API_KEY=sk-test-42" in env_text


@pytest.mark.parametrize("name", ["HERCULES_MODEL_API_KEY", "HERCULES_DELEGATION_API_KEY",
                                  "HERCULES_CUSTOM_LAB_API_KEY", "AUXILIARY_VISION_API_KEY"])
def test_child_env_strips_moved_credentials(name):
    from tools.environments.local import _is_hercules_internal_secret
    assert _is_hercules_internal_secret(name)


def test_child_env_keeps_ordinary_settings():
    from tools.environments.local import _is_hercules_internal_secret
    assert not _is_hercules_internal_secret("HERCULES_MODEL")


def test_custom_endpoint_key_goes_to_env(tmp_path, monkeypatch):
    """A new custom_providers entry stores its key in .env and keeps a reference in config.yaml."""
    monkeypatch.setenv("HERCULES_HOME", str(tmp_path))
    from hercules_cli.main import _save_custom_provider

    _save_custom_provider("http://localhost:8080/v1", api_key="sk-lab-77", model="m1", name="lab")

    yaml_text = (tmp_path / "config.yaml").read_text(encoding="utf-8")
    env_text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "sk-lab-77" not in yaml_text
    assert "${HERCULES_CUSTOM_LOCALHOST_8080_API_KEY}" in yaml_text
    assert "HERCULES_CUSTOM_LOCALHOST_8080_API_KEY=sk-lab-77" in env_text
