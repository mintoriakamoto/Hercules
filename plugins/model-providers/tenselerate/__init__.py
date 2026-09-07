"""Cooklabs TENSELERATE — local llama.cpp SVMI (llama-server).

Default endpoint http://127.0.0.1:8080/v1 (OpenAI-compat).
hercules doctor probes {base_url}/models. No cloud key required.
"""

from typing import Any

from providers import register_provider
from providers.base import ProviderProfile


class TenselerateProfile(ProviderProfile):
    """Local TENSELERATE llama-server. Same request quirks as custom/llama.cpp."""

    def build_api_kwargs_extras(
        self,
        *,
        reasoning_config: dict | None = None,
        **ctx: Any,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        extra_body: dict[str, Any] = {}
        top_level: dict[str, Any] = {}
        if reasoning_config and isinstance(reasoning_config, dict):
            effort = (reasoning_config.get("effort") or "").strip().lower()
            enabled = reasoning_config.get("enabled", True)
            if effort == "none" or enabled is False:
                extra_body["think"] = False
            elif effort:
                top_level["reasoning_effort"] = effort
        return extra_body, top_level

    def fetch_models(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 8.0,
    ) -> list[str] | None:
        return super().fetch_models(
            api_key=api_key,
            base_url=base_url or self.base_url,
            timeout=timeout,
        )


tenselerate = TenselerateProfile(
    name="tenselerate",
    aliases=("svmi", "llama-server", "tenselerate-local"),
    display_name="TENSELERATE",
    description="Cooklabs local llama-server SVMI (default :8080)",
    signup_url="https://github.com/mintoriakamoto/TENSELERATE-",
    env_vars=(),
    base_url="http://127.0.0.1:8080/v1",
    models_url="http://127.0.0.1:8080/v1/models",
    auth_type="api_key",
    supports_health_check=True,
    default_max_tokens=65536,
    hostname="127.0.0.1",
)

register_provider(tenselerate)
