"""Cooklabs TENSELERATE — local llama.cpp SVMI server.

Default endpoint is llama-server on 127.0.0.1:8080 (OpenAI-compat).
Doctor probes {base_url}/models. No cloud key.
"""

from plugins.model_providers_custom import CustomProfile  # type: ignore
