"""Tests for scripts/check_secrets.py (the pre-commit secret guard)."""

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "check_secrets", Path(__file__).resolve().parents[2] / "scripts" / "check_secrets.py"
)
check_secrets = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(check_secrets)

# Built at runtime so this file never holds a key-shaped literal itself.
# Varied characters so they are not skipped as placeholders.
FAKE_OPENROUTER = "sk-or-v1-" + "9f3c7a1e5b" * 7
FAKE_GITHUB = "ghp_" + "Qw7rT2yU9i" * 4


def test_flags_provider_key_by_rule_not_value():
    findings = check_secrets.scan_text(f"OPENROUTER_API_KEY={FAKE_OPENROUTER}\n")
    assert findings == [(1, "OpenRouter key")]


def test_allow_marker_skips_fixture_line():
    text = f'token = "{FAKE_GITHUB}"  # secret-scan: allow\n'
    assert check_secrets.scan_text(text) == []


def test_documented_example_keys_pass():
    assert check_secrets.scan_text("AKIA" + "IOSFODNN7EXAMPLE") == []


def test_placeholders_pass():
    text = "ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}\nOPENAI_API_KEY=your-key-here\n"
    assert check_secrets.scan_text(text) == []


def test_env_files_blocked_except_example():
    assert check_secrets.is_forbidden_env_file(".env")
    assert check_secrets.is_forbidden_env_file(".env.unrestricted")
    assert check_secrets.is_forbidden_env_file("deploy/.env.production")
    assert not check_secrets.is_forbidden_env_file(".env.example")
    assert not check_secrets.is_forbidden_env_file(".envrc")
    assert not check_secrets.is_forbidden_env_file("agent/env_loader.py")


def test_main_output_never_contains_the_value(tmp_path, capsys):
    f = tmp_path / "config.py"
    f.write_text(f'KEY = "{FAKE_OPENROUTER}"\n')
    assert check_secrets.main([str(f)]) == 1
    out = capsys.readouterr().out
    assert "OpenRouter key" in out
    assert FAKE_OPENROUTER not in out
    assert FAKE_OPENROUTER[9:20] not in out
