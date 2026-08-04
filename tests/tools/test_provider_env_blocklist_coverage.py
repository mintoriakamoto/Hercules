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
]

# Third-party API keys that must stay OFF the blocklist. The list has a second
# consumer with the opposite meaning: tools/env_passthrough.py treats
# membership as "no skill may ever register this for passthrough" (the fix for
# GHSA-rhgp-j443-p4rf). Adding a third-party key here does not just scrub it
# from subprocesses — it breaks every skill wrapping that API.
THIRD_PARTY_KEYS_THAT_MUST_STAY_REGISTERABLE = [
    "NOTION_API_KEY",
    "LINEAR_API_KEY",
    "TENOR_API_KEY",
    "NOTION_TOKEN",
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


@pytest.mark.parametrize("name", THIRD_PARTY_KEYS_THAT_MUST_STAY_REGISTERABLE)
def test_third_party_keys_stay_off_the_blocklist(name):
    """Guards the regression this file's own first draft introduced.

    Adding NOTION_API_KEY / LINEAR_API_KEY here looked like tightening the
    scrubber. It actually revoked skills' ability to declare them via
    ``env_passthrough``, because env_passthrough.py reads the same list as an
    absolute denial. A skill wrapping the Notion API stopped working.
    """
    assert name not in _HERCULES_PROVIDER_ENV_BLOCKLIST


@pytest.mark.parametrize("name", THIRD_PARTY_KEYS_THAT_MUST_STAY_REGISTERABLE)
def test_third_party_keys_remain_registerable_for_passthrough(name):
    """The property that actually matters, asserted against the real gate."""
    from tools.env_passthrough import _is_hercules_provider_credential

    assert _is_hercules_provider_credential(name) is False


@pytest.mark.parametrize("name", DRIFTED_CREDENTIALS)
def test_hercules_credentials_are_not_registerable_for_passthrough(name):
    """The other half: a skill must not be able to tunnel a Hercules
    credential into a sandbox child (GHSA-rhgp-j443-p4rf)."""
    from tools.env_passthrough import _is_hercules_provider_credential

    assert _is_hercules_provider_credential(name) is True


def test_session_key_is_a_routing_handle_not_a_secret():
    """SECURITY.md §2.6: session identifiers are routing handles. The approval
    cache scopes to it, so stripping it would break per-session scoping."""
    env = {"HERCULES_SESSION_KEY": "abc123", "PATH": "/usr/bin"}
    assert "HERCULES_SESSION_KEY" in _sanitize_subprocess_env(env)
