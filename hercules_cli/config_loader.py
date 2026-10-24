"""
API Configuration Loader for Hercules

Loads and validates API configuration from:
1. ~/.hercules/config.yaml (file-based config)
2. Environment variables (HERCULES_* overrides)
3. Constructor parameters (highest priority)

Provides helpful error messages when config is missing or invalid.
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ConfigError(ValueError):
    """Configuration validation error with helpful guidance."""
    pass


class ConfigLoader:
    """Load and validate Hercules API configuration."""

    # Supported providers
    SUPPORTED_PROVIDERS = {
        "anthropic": {
            "required_fields": ["model", "api_key"],
            "optional_fields": ["base_url"],
            "default_base_url": "https://api.anthropic.com"
        },
        "openrouter": {
            "required_fields": ["model", "api_key"],
            "optional_fields": ["base_url"],
            "default_base_url": "https://openrouter.io/api/v1"
        },
        "ollama": {
            "required_fields": ["model"],
            "optional_fields": ["api_key", "base_url"],
            "default_base_url": "http://localhost:11434"
        },
    }

    @staticmethod
    def load(
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        provider: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Load and validate API configuration.

        Priority order:
        1. Constructor parameters (highest priority)
        2. Environment variables
        3. Config file (~/.hercules/config.yaml)
        4. Defaults

        Args:
            model: Model name (e.g., "claude-opus-4-20250514")
            api_key: API key for the provider
            provider: Provider name ("anthropic", "openrouter", "ollama")
            base_url: Custom API base URL

        Returns:
            Dict with validated config: {model, api_key, provider, base_url}

        Raises:
            ConfigError: If required fields are missing or invalid
        """
        config = {}

        # Step 1: Load from config file
        config_file = Path.home() / ".hercules" / "config.yaml"
        if config_file.exists():
            try:
                import yaml
                file_config = yaml.safe_load(config_file.read_text())
                if file_config and isinstance(file_config, dict):
                    config.update(file_config)
                    logger.debug(f"Loaded config from {config_file}")
            except Exception as e:
                logger.warning(f"Failed to load config file {config_file}: {e}")

        # Step 2: Override with environment variables
        env_model = os.getenv("HERCULES_MODEL")
        env_api_key = os.getenv("HERCULES_API_KEY")
        env_provider = os.getenv("HERCULES_PROVIDER")
        env_base_url = os.getenv("HERCULES_BASE_URL")

        if env_model:
            config["model"] = env_model
        if env_api_key:
            config["api_key"] = env_api_key
        if env_provider:
            config["provider"] = env_provider
        if env_base_url:
            config["base_url"] = env_base_url

        # Step 3: Override with constructor parameters (highest priority)
        if model:
            config["model"] = model
        if api_key:
            config["api_key"] = api_key
        if provider:
            config["provider"] = provider
        if base_url:
            config["base_url"] = base_url

        # Step 4: Validate required fields
        ConfigLoader._validate_config(config)

        # Step 5: Apply defaults
        if "provider" not in config:
            config["provider"] = "anthropic"

        provider_name = config["provider"].lower()
        if provider_name not in ConfigLoader.SUPPORTED_PROVIDERS:
            raise ConfigError(
                f"Unknown provider: {provider_name}\n"
                f"Supported providers: {', '.join(ConfigLoader.SUPPORTED_PROVIDERS.keys())}"
            )

        provider_spec = ConfigLoader.SUPPORTED_PROVIDERS[provider_name]
        if "base_url" not in config:
            config["base_url"] = provider_spec["default_base_url"]

        return config

    @staticmethod
    def _validate_config(config: Dict[str, Any]) -> None:
        """
        Validate configuration and raise ConfigError with helpful messages.

        Args:
            config: Configuration dict to validate

        Raises:
            ConfigError: If validation fails
        """
        # Check model
        if not config.get("model"):
            raise ConfigError(
                "No model specified. Hercules needs a model to run.\n\n"
                "Set it via one of these methods:\n\n"
                "  1. Environment variable:\n"
                "     export HERCULES_MODEL=claude-opus-4-20250514\n\n"
                "  2. Config file (~/.hercules/config.yaml):\n"
                "     model: claude-opus-4-20250514\n"
                "     api_key: sk-ant-...\n\n"
                "  3. Constructor parameter:\n"
                "     agent = AIAgent(model='claude-opus-4-20250514')\n\n"
                "Common Claude models:\n"
                "  - claude-opus-4-20250514\n"
                "  - claude-sonnet-4-20250514\n"
                "  - claude-haiku-3-5-20241022\n"
            )

        # Check API key (optional for some providers like Ollama)
        provider = config.get("provider", "anthropic").lower()
        if provider != "ollama" and not config.get("api_key"):
            raise ConfigError(
                f"No API key for {provider}. Provider '{provider}' requires authentication.\n\n"
                "Set it via one of these methods:\n\n"
                "  1. Environment variable:\n"
                "     export HERCULES_API_KEY=sk-ant-...\n\n"
                "  2. Config file (~/.hercules/config.yaml):\n"
                "     api_key: sk-ant-...\n\n"
                "  3. Constructor parameter:\n"
                "     agent = AIAgent(api_key='sk-ant-...')\n"
            )

    @staticmethod
    def create_example_config() -> str:
        """Generate example config file content."""
        return """# Hercules API Configuration
# Save this to ~/.hercules/config.yaml

# Model to use
# Anthropic models: claude-opus-4-20250514, claude-sonnet-4-20250514, claude-haiku-3-5-20241022
# OpenRouter models: See https://openrouter.ai/models
model: claude-opus-4-20250514

# API provider: anthropic, openrouter, or ollama
provider: anthropic

# API key (required for Anthropic and OpenRouter, optional for Ollama)
api_key: sk-ant-...

# Optional: Custom API base URL (uncomment if needed)
# base_url: https://api.anthropic.com

# Optional: Model-specific settings (passed to API)
# max_tokens: 4096
# temperature: 0.7
"""

    @staticmethod
    def ensure_config_dir() -> Path:
        """Create ~/.hercules directory if it doesn't exist."""
        config_dir = Path.home() / ".hercules"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir

    @staticmethod
    def setup_example_config() -> None:
        """Create example config file if it doesn't exist."""
        config_dir = ConfigLoader.ensure_config_dir()
        config_file = config_dir / "config.yaml"

        if not config_file.exists():
            config_file.write_text(ConfigLoader.create_example_config())
            logger.info(f"Created example config file at {config_file}")
            logger.info("Please edit it with your API key and model preference")
