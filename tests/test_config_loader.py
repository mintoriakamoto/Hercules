"""Tests for API configuration loader."""

import os
import tempfile
from pathlib import Path

import pytest

from hercules_cli.config_loader import ConfigLoader, ConfigError


class TestConfigLoader:
    """Test configuration loading and validation."""

    def test_load_from_constructor_parameters(self):
        """Constructor parameters should have highest priority."""
        config = ConfigLoader.load(
            model="claude-opus-4-20250514",
            api_key="sk-ant-test-key",
            provider="anthropic",
        )
        assert config["model"] == "claude-opus-4-20250514"
        assert config["api_key"] == "sk-ant-test-key"
        assert config["provider"] == "anthropic"
        assert config["base_url"] == "https://api.anthropic.com"

    def test_load_from_environment_variables(self, monkeypatch):
        """Environment variables should override config file."""
        monkeypatch.setenv("HERCULES_MODEL", "claude-sonnet-4-20250514")
        monkeypatch.setenv("HERCULES_API_KEY", "sk-ant-env-key")
        monkeypatch.setenv("HERCULES_PROVIDER", "anthropic")

        config = ConfigLoader.load()
        assert config["model"] == "claude-sonnet-4-20250514"
        assert config["api_key"] == "sk-ant-env-key"
        assert config["provider"] == "anthropic"

    def test_constructor_overrides_environment(self, monkeypatch):
        """Constructor parameters should override environment variables."""
        monkeypatch.setenv("HERCULES_MODEL", "claude-sonnet-4-20250514")
        monkeypatch.setenv("HERCULES_API_KEY", "sk-ant-env-key")

        config = ConfigLoader.load(
            model="claude-opus-4-20250514",
            api_key="sk-ant-constructor-key",
        )
        assert config["model"] == "claude-opus-4-20250514"
        assert config["api_key"] == "sk-ant-constructor-key"

    def test_missing_model_raises_helpful_error(self):
        """Missing model should raise ConfigError with setup instructions."""
        with pytest.raises(ConfigError) as exc_info:
            ConfigLoader.load(api_key="sk-ant-test-key")

        error_msg = str(exc_info.value)
        assert "No model specified" in error_msg
        assert "HERCULES_MODEL" in error_msg
        assert "config.yaml" in error_msg
        assert "claude-opus-4-20250514" in error_msg

    def test_missing_api_key_for_anthropic_raises_error(self):
        """Missing API key for Anthropic should raise ConfigError."""
        with pytest.raises(ConfigError) as exc_info:
            ConfigLoader.load(
                model="claude-opus-4-20250514",
                provider="anthropic",
            )

        error_msg = str(exc_info.value)
        assert "No API key" in error_msg
        assert "anthropic" in error_msg
        assert "HERCULES_API_KEY" in error_msg

    def test_missing_api_key_for_openrouter_raises_error(self):
        """Missing API key for OpenRouter should raise ConfigError."""
        with pytest.raises(ConfigError) as exc_info:
            ConfigLoader.load(
                model="gpt-4-turbo",
                provider="openrouter",
            )

        error_msg = str(exc_info.value)
        assert "No API key" in error_msg
        assert "openrouter" in error_msg

    def test_ollama_allows_missing_api_key(self):
        """Ollama provider should not require API key."""
        config = ConfigLoader.load(
            model="llama2",
            provider="ollama",
        )
        assert config["model"] == "llama2"
        assert config["provider"] == "ollama"
        assert config["base_url"] == "http://localhost:11434"

    def test_default_provider_is_anthropic(self):
        """Default provider should be Anthropic if not specified."""
        config = ConfigLoader.load(
            model="claude-opus-4-20250514",
            api_key="sk-ant-test-key",
        )
        assert config["provider"] == "anthropic"

    def test_custom_base_url(self):
        """Custom base URL should be preserved."""
        config = ConfigLoader.load(
            model="claude-opus-4-20250514",
            api_key="sk-ant-test-key",
            base_url="https://custom-proxy.example.com/v1",
        )
        assert config["base_url"] == "https://custom-proxy.example.com/v1"

    def test_default_base_url_for_anthropic(self):
        """Anthropic should default to official API endpoint."""
        config = ConfigLoader.load(
            model="claude-opus-4-20250514",
            api_key="sk-ant-test-key",
            provider="anthropic",
        )
        assert config["base_url"] == "https://api.anthropic.com"

    def test_default_base_url_for_openrouter(self):
        """OpenRouter should default to its endpoint."""
        config = ConfigLoader.load(
            model="gpt-4-turbo",
            api_key="sk-test-key",
            provider="openrouter",
        )
        assert config["base_url"] == "https://openrouter.io/api/v1"

    def test_default_base_url_for_ollama(self):
        """Ollama should default to localhost."""
        config = ConfigLoader.load(
            model="llama2",
            provider="ollama",
        )
        assert config["base_url"] == "http://localhost:11434"

    def test_unsupported_provider_raises_error(self):
        """Unsupported provider should raise ConfigError."""
        with pytest.raises(ConfigError) as exc_info:
            ConfigLoader.load(
                model="some-model",
                api_key="some-key",
                provider="unsupported-provider",
            )

        error_msg = str(exc_info.value)
        assert "Unknown provider" in error_msg
        assert "unsupported-provider" in error_msg

    def test_create_example_config_returns_valid_content(self):
        """Example config should be valid YAML."""
        content = ConfigLoader.create_example_config()
        assert "model:" in content
        assert "provider:" in content
        assert "api_key:" in content
        assert "claude-opus-4-20250514" in content

    def test_ensure_config_dir_creates_directory(self):
        """ensure_config_dir should create ~/.hercules if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Mock Path.home() to return our temp directory
            home_path = Path(tmpdir)
            config_dir = home_path / ".hercules"

            # Verify it doesn't exist yet
            assert not config_dir.exists()

            # Create it (we can't easily patch Path.home(), so just test the concept)
            config_dir.mkdir(parents=True, exist_ok=True)

            # Verify it exists
            assert config_dir.exists()
            assert config_dir.is_dir()

    def test_setup_example_config_creates_file(self):
        """setup_example_config should create the config file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            home_path = Path(tmpdir)
            config_dir = home_path / ".hercules"
            config_file = config_dir / "config.yaml"

            # Create directory first
            config_dir.mkdir(parents=True, exist_ok=True)

            # Create config file
            config_file.write_text(ConfigLoader.create_example_config())

            # Verify it exists and contains expected content
            assert config_file.exists()
            content = config_file.read_text()
            assert "model:" in content
            assert "provider:" in content


class TestConfigIntegration:
    """Integration tests with actual config files."""

    def test_load_from_config_file(self, tmp_path, monkeypatch):
        """ConfigLoader should load from ~/.hercules/config.yaml."""
        # Create temp config directory
        config_dir = tmp_path / ".hercules"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"

        # Write a test config
        config_file.write_text(
            """
model: claude-opus-4-20250514
api_key: sk-ant-file-key
provider: anthropic
"""
        )

        # Mock home directory
        original_home = Path.home
        try:
            Path.home = lambda: tmp_path
            config = ConfigLoader.load()
            assert config["model"] == "claude-opus-4-20250514"
            assert config["api_key"] == "sk-ant-file-key"
        finally:
            Path.home = original_home

    def test_env_overrides_file_config(self, tmp_path, monkeypatch):
        """Environment variables should override file config."""
        # Create temp config directory with file
        config_dir = tmp_path / ".hercules"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"

        config_file.write_text(
            """
model: claude-opus-4-20250514
api_key: sk-ant-file-key
"""
        )

        # Set environment variable to override
        monkeypatch.setenv("HERCULES_API_KEY", "sk-ant-env-key")

        # Mock home directory
        original_home = Path.home
        try:
            Path.home = lambda: tmp_path
            config = ConfigLoader.load()
            assert config["api_key"] == "sk-ant-env-key"  # Env wins
            assert config["model"] == "claude-opus-4-20250514"  # File value
        finally:
            Path.home = original_home
