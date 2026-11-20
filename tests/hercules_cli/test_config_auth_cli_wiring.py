"""End-to-end wiring for ``hercules config`` and ``hercules auth``.

Both commands were once re-registered from ``hercules_cli/commands/`` stubs
whose handlers only logged, so ``hercules config set`` exited 0 without
writing anything (and the docker privilege-drop tests, which rely on it,
failed). These tests run the real CLI entry point in a subprocess so a stub
parser cannot shadow the real one again unnoticed.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def _run(args, home: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["HERCULES_HOME"] = str(home)
    env.pop("HERCULES_MANAGED", None)
    return subprocess.run(
        [sys.executable, "-m", "hercules_cli.main", *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_config_set_writes_config_yaml(tmp_path):
    r = _run(["config", "set", "_test.shim_marker", "1"], tmp_path)
    assert r.returncode == 0, r.stderr
    config_path = tmp_path / "config.yaml"
    assert config_path.exists(), f"config set wrote nothing: {r.stdout!r}"
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert data["_test"]["shim_marker"] == 1


def test_config_path_prints_config_location(tmp_path):
    r = _run(["config", "path"], tmp_path)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == str(tmp_path / "config.yaml")


def test_auth_exposes_credential_pool_subcommands(tmp_path):
    r = _run(["auth", "--help"], tmp_path)
    assert r.returncode == 0, r.stderr
    for sub in ("add", "list", "remove", "reset", "status"):
        assert sub in r.stdout, f"'hercules auth {sub}' missing: {r.stdout!r}"
