from pathlib import Path

from hercules_cli.hermes_migrate import apply, plan


def test_plan_and_apply(tmp_path: Path):
    src = tmp_path / ".hermes"
    dst = tmp_path / ".hercules"
    (src / "skills" / "foo").mkdir(parents=True)
    (src / "skills" / "foo" / "SKILL.md").write_text("# foo\n")
    (src / "config.yaml").write_text("model: local\n")
    items = plan(src, dst, secrets=False)
    kinds = {i[0] for i in items}
    assert "dir" in kinds
    assert "file" in kinds
    done = apply(items, overwrite=True)
    assert any("copy" in line for line in done)
    assert (dst / "skills" / "hermes-imports" / "foo" / "SKILL.md").is_file()
    assert (dst / "imports" / "hermes-config.yaml").is_file()
