"""Credential env vars must not reach terminal / execute_code children.

``SECURITY.md`` §2.3 states that provider API keys and gateway tokens are
stripped from lower-trust in-process components by default. The blocklist is
derived from ``PROVIDER_REGISTRY`` and ``OPTIONAL_ENV_VARS``, so an integration
that reads a credential via ``os.getenv`` without declaring it in
``OPTIONAL_ENV_VARS`` silently escapes that derivation.

These tests pin the specific names that had drifted, and assert the two
deliberate exclusions stay excluded.
"""

import pytest

from tools.code_execution_tool import _scrub_child_env
from tools.environments.local import (
    _HERCULES_PROVIDER_ENV_BLOCKLIST,
    _sanitize_subprocess_env,
)

# Each of these had a *less* sensitive sibling already on the blocklist
# (CAMOFOX_URL, FEISHU_APP_ID, TELEGRAM_ALLOWED_USERS …), which is what marks
# them as drift rather than a decision.
DRIFTED_CREDENTIALS = [
    "TELEGRAM_WEBHOOK_SECRET",
    "WHATSAPP_CLOUD_ACCESS_TOKEN",
    "WHATSAPP_CLOUD_APP_SECRET",
    "WHATSAPP_CLOUD_VERIFY_TOKEN",
    "FEISHU_ENCRYPT_KEY",
    "FEISHU_VERIFICATION_TOKEN",
    "TEAMS_GRAPH_ACCESS_TOKEN",
    "PHOTON_SIDECAR_TOKEN",
    "QQ_STT_API_KEY",
    "CAMOFOX_SESSION_KEY",
    "WEIXIN_TOKEN",
    "YUANBAO_APP_KEY",
    "YUANBAO_APP_SECRET",
    "AZURE_ANTHROPIC_KEY",
    "CUSTOM_API_KEY",
    "LINEAR_API_KEY",
    "NOTION_API_KEY",
]

# Documented carve-outs. Both look like secrets and are not.
INTENTIONALLY_INHERITED = [
    # #55878 — owned by the user's Claude Code install. Stripping it made
    # agent-spawned `claude` CLIs clear the shared credential store on auth
    # failure, logging the user out of interactive sessions.
    "CLAUDE_CODE_OAUTH_TOKEN",
    # A published installed-app constant shipped by every gemini-cli install;
    # kept out of the source only to avoid secret-scanner noise.
    "GEMINI_OAUTH_CLIENT_SECRET",
]


@pytest.mark.parametrize("name", DRIFTED_CREDENTIALS)
def test_credential_is_on_the_blocklist(name):
    assert name in _HERCULES_PROVIDER_ENV_BLOCKLIST


@pytest.mark.parametrize("name", DRIFTED_CREDENTIALS)
def test_credential_stripped_from_terminal_children(name):
    env = {name: "SECRET-VALUE", "PATH": "/usr/bin"}
    assert name not in _sanitize_subprocess_env(env)


@pytest.mark.parametrize("name", DRIFTED_CREDENTIALS)
def test_both_spawn_paths_agree(name):
    """execute_code and terminal must not disagree about a credential.

    The two use different mechanisms — substring matching vs. a name list —
    and that asymmetry is what let these through on the terminal path only.
    """
    env = {name: "SECRET-VALUE", "PATH": "/usr/bin"}
    assert (name in _scrub_child_env(dict(env))) == (
        name in _sanitize_subprocess_env(dict(env))
    )


@pytest.mark.parametrize("name", INTENTIONALLY_INHERITED)
def test_documented_carve_outs_still_inherited(name):
    """Guards the regression that adding these back would reintroduce."""
    env = {name: "VALUE", "PATH": "/usr/bin"}
    assert name in _sanitize_subprocess_env(env)
    assert name not in _HERCULES_PROVIDER_ENV_BLOCKLIST


def test_session_key_is_a_routing_handle_not_a_secret():
    """SECURITY.md §2.6: session identifiers are routing handles. The approval
    cache scopes to it, so stripping it would break per-session scoping."""
    env = {"HERCULES_SESSION_KEY": "abc123", "PATH": "/usr/bin"}
    assert "HERCULES_SESSION_KEY" in _sanitize_subprocess_env(env)
