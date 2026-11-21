"""Config writers keep credentials in ``.env`` and store only a reference in ``config.yaml``.

``config.yaml`` holds settings; ``.env`` holds secrets. ``hercules config set`` on a credential
path (``model.api_key``, ``delegation.api_key``, ``auxiliary.<task>.api_key``,
``providers.<name>.api_key``, ``custom_providers.<N>.api_key``) saves the literal value to ``.env``
under a deterministic name and writes ``${NAME}`` in the field. ``load_config`` expands the
reference, so resolution is unchanged. Inline values already in a config keep working; nothing is
migrated.
"""

from __future__ import annotations

import re
import sys
import urllib.parse
from typing import Any, Optional

_ENV_REF_ONLY_RE = re.compile(r"^\$\{[^}]+\}$")


def _env_slug(text: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", str(text or "").upper()).strip("_")


def model_api_key_env() -> str:
    return "HERCULES_MODEL_API_KEY"


def aux_api_key_env(task: str) -> str:
    """``AUXILIARY_<TASK>_API_KEY``; ``delegation`` gets ``HERCULES_DELEGATION_API_KEY``."""
    if task == "delegation":
        return "HERCULES_DELEGATION_API_KEY"
    return f"AUXILIARY_{_env_slug(task) or 'TASK'}_API_KEY"


def custom_endpoint_key_env(name: str) -> str:
    """``HERCULES_CUSTOM_<NAME>_API_KEY`` for a named custom endpoint."""
    return f"HERCULES_CUSTOM_{_env_slug(name) or 'ENDPOINT'}_API_KEY"


def endpoint_api_key_env(base_url: str) -> str:
    """Variable for a custom endpoint keyed by host[:port][/path], so two servers on one machine
    keep separate credentials. Falls back to the model key when the URL has no host."""
    parsed = urllib.parse.urlparse(str(base_url or "").strip())
    identity = parsed.hostname or ""
    if parsed.port:
        identity = f"{identity}_{parsed.port}"
    path = parsed.path.strip("/")
    if identity and path and path.lower() != "v1":
        identity = f"{identity}_{path}"
    return custom_endpoint_key_env(identity) if identity else model_api_key_env()


def is_env_reference(value: Any) -> bool:
    return isinstance(value, str) and bool(_ENV_REF_ONLY_RE.match(value.strip()))


def is_secret_config_key(key: str) -> bool:
    """True when the last segment of a dotted config key names a credential."""
    last = str(key or "").strip().lower().rsplit(".", 1)[-1]
    return last.endswith(("api_key", "_token", "token", "secret", "password"))


def store_secret(env_name: str, value: str) -> str:
    """Save ``value`` to ``.env`` as ``env_name`` and return the ``${env_name}`` reference."""
    import os

    from hercules_cli.config import save_env_value

    save_env_value(env_name, value)
    os.environ[env_name] = value  # visible to this process before the next load
    return f"${{{env_name}}}"


def secret_ref_for(env_name: str, value: Any) -> Any:
    """The value a writer should persist for a credential field: ``${env_name}`` after a literal
    secret is saved to ``.env``. Empty values, existing references and non-strings pass through."""
    if not isinstance(value, str) or not value.strip() or is_env_reference(value):
        return value
    return store_secret(env_name, value.strip())


def _custom_provider_entry_name(user_config: dict, index: str) -> str:
    entries = user_config.get("custom_providers")
    if isinstance(entries, list) and index.isdigit() and int(index) < len(entries):
        entry = entries[int(index)]
        if isinstance(entry, dict) and str(entry.get("name") or "").strip():
            return str(entry["name"])
    return f"custom_providers_{index}"


def config_path_api_key_env(parts: list[str], user_config: dict) -> Optional[str]:
    """The ``.env`` name for a credential config path, or None for paths written as given."""
    if not parts or parts[-1] != "api_key":
        return None
    head = parts[:-1]
    if head == ["model"]:
        return model_api_key_env()
    if head == ["delegation"]:
        return aux_api_key_env("delegation")
    if len(head) == 2 and head[0] == "auxiliary":
        return aux_api_key_env(head[1])
    if len(head) == 2 and head[0] == "providers":
        return custom_endpoint_key_env(head[1])
    if len(head) == 2 and head[0] == "custom_providers":
        return custom_endpoint_key_env(_custom_provider_entry_name(user_config, head[1]))
    return None


def config_set_secret_value(key: str, value: Any, user_config: dict) -> Any:
    """The value ``hercules config set`` writes at ``key``: a literal secret on a credential path is
    saved to ``.env`` (a note names the variable) and its reference is returned. A failed ``.env``
    write exits without changing config.yaml."""
    env_name = config_path_api_key_env(str(key).split("."), user_config)
    if env_name is None:
        return value
    try:
        stored = secret_ref_for(env_name, value)
    except (OSError, ValueError) as exc:
        print(f"✗ Could not save the secret to .env as {env_name}: {exc}", file=sys.stderr)
        sys.exit(1)
    if stored != value:
        print(f"  (secret saved to .env as {env_name}; config.yaml stores the reference {stored})")
    return stored


def masked_display_value(key: str, value: Any) -> Any:
    """The value echoed after a set: masked for a credential key, references shown as they are."""
    if is_secret_config_key(key) and isinstance(value, str) and value and not is_env_reference(value):
        from agent.redact import mask_secret

        return mask_secret(value)
    return value
