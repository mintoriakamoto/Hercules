"""Copy a local Nous Hermes Agent home into ~/.hercules.

Does not pull github.com/NousResearch/hermes-agent.
Copies skills + config.yaml. .env only with --secrets.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

HOME = Path.home()
DEFAULT_SRC = Path(HOME / ".hermes")
DEFAULT_DST = Path(HOME / ".hercules")


def plan(src: Path, dst: Path, *, secrets: bool) -> list[tuple[str, Path, Path]]:
    items: list[tuple[str, Path, Path]] = []
    skills = src / "skills"
    if skills.is_dir():
        items.append(("dir", skills, dst / "skills" / "hermes-imports"))
    cfg = src / "config.yaml"
    if cfg.is_file():
        items.append(("file", cfg, dst / "imports" / "hermes-config.yaml"))
    env = src / ".env"
    if secrets and env.is_file():
        items.append(("file", env, dst / "imports" / "hermes.env"))
    return items


def apply(items: list[tuple[str, Path, Path]], *, overwrite: bool) -> list[str]:
    done: list[str] = []
    for kind, src, dst in items:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists() and not overwrite:
            done.append(f"skip {dst}")
            continue
        if kind == "dir":
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        done.append(f"copy {src} → {dst}")
    return done


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import ~/.hermes into ~/.hercules")
    parser.add_argument("--source", type=Path, default=DEFAULT_SRC)
    parser.add_argument("--dest", type=Path, default=DEFAULT_DST)
    parser.add_argument("--secrets", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    src = args.source.expanduser()
    dst = args.dest.expanduser()
    if not src.is_dir():
        print(f"no Hermes home at {src}")
        return 1
    items = plan(src, dst, secrets=args.secrets)
    if not items:
        print(f"nothing to import from {src}")
        return 0
    print(f"from {src}")
    print(f"into {dst}")
    for kind, a, b in items:
        print(f"  {kind:4} {a} → {b}")
    if args.dry_run:
        print("dry-run")
        return 0
    for line in apply(items, overwrite=args.overwrite):
        print(line)
    print("done. inference stays TENSELERATE; origin stays mintoriakamoto/Hercules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
