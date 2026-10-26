"""skills.auto_load pins listed skills as fully loaded blocks in every new
session's system prompt."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from agent.skill_commands import build_auto_load_prompt, resolve_auto_load_skills


def _make_skill(skills_dir, name, body="Do the thing."):
    skill_dir = skills_dir / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Description for {name}.\n---\n\n# {name}\n\n{body}\n"
    )


@pytest.mark.parametrize(
    "config,expected",
    [
        ({}, []),
        ({"skills": {}}, []),
        ({"skills": {"auto_load": "not-a-list"}}, []),
        ({"skills": {"auto_load": [" a ", "b", "a", "", 3]}}, ["a", "b"]),
        ("garbage", []),
    ],
)
def test_resolve_auto_load_skills(config, expected):
    assert resolve_auto_load_skills(config) == expected


def test_build_auto_load_prompt_renders_and_reports_missing(tmp_path):
    with patch("tools.skills_tool.SKILLS_DIR", tmp_path):
        _make_skill(tmp_path, "pinned-skill", body="PINNED BODY MARKER")
        prompt, loaded, missing = build_auto_load_prompt(
            user_config={"skills": {"auto_load": ["pinned-skill", "no-such-skill"]}}
        )
    assert loaded == ["pinned-skill"]
    assert missing == ["no-such-skill"]
    assert "PINNED BODY MARKER" in prompt
    assert "auto-loaded via config (skills.auto_load)" in prompt
    assert "launched this CLI session" not in prompt


def test_empty_config_renders_nothing():
    assert build_auto_load_prompt(user_config={"skills": {"auto_load": []}}) == (
        "",
        [],
        [],
    )


def test_system_prompt_part_is_resolved_once_and_respects_ignore_rules(monkeypatch):
    from agent import system_prompt as sp

    calls = []

    def fake_build(task_id=None, user_config=None):
        calls.append(task_id)
        return ("PINNED", ["x"], [])

    monkeypatch.setattr("agent.skill_commands.build_auto_load_prompt", fake_build)
    agent = SimpleNamespace(session_id="s1")
    assert sp._auto_load_parts(agent) == ["PINNED"]
    assert sp._auto_load_parts(agent) == ["PINNED"]
    assert calls == ["s1"]  # cached per agent

    monkeypatch.setenv("HERCULES_IGNORE_RULES", "1")
    fresh = SimpleNamespace(session_id="s2")
    assert sp._auto_load_parts(fresh) == []
    assert calls == ["s1"]


def test_config_error_never_blocks_prompt_build(monkeypatch):
    from agent import system_prompt as sp

    def boom(task_id=None, user_config=None):
        raise RuntimeError("bad config")

    monkeypatch.setattr("agent.skill_commands.build_auto_load_prompt", boom)
    assert sp._auto_load_parts(SimpleNamespace(session_id="s3")) == []


def test_preload_note_unchanged_for_cli_preloading(tmp_path):
    from agent.skill_commands import build_preloaded_skills_prompt

    with patch("tools.skills_tool.SKILLS_DIR", tmp_path):
        _make_skill(tmp_path, "cli-skill")
        prompt, loaded, _ = build_preloaded_skills_prompt(["cli-skill"])
    assert loaded == ["cli-skill"]
    assert 'launched this CLI session with the "cli-skill" skill' in prompt
