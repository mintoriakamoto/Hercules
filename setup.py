from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import tempfile
import sys

from setuptools import setup
from setuptools.command.build import build as _build
from setuptools.command.egg_info import egg_info as _egg_info


REPO_ROOT = Path(__file__).parent.resolve()


def _pyproject_is_placeholder() -> bool:
    """Check if pyproject.toml contains only PLACEHOLDER token."""
    pyproject = REPO_ROOT / "pyproject.toml"
    if not pyproject.exists():
        return False
    return pyproject.read_text(encoding="utf-8").strip() == "PLACEHOLDER"


# Fallback metadata for PLACEHOLDER mode during development/refactoring
PLACEHOLDER_METADATA = {
    "name": "hercules-agent",
    "version": "1.0.0",
    "description": "The self-improving AI agent — creates skills from experience, improves them during use, and runs anywhere",
    "long_description": (REPO_ROOT / "README.md").read_text(encoding="utf-8") if (REPO_ROOT / "README.md").exists() else "",
    "long_description_content_type": "text/markdown",
    "url": "https://github.com/mintoriakamoto/Hercules",
    "author": "Nous Research",
    "license": "MIT",
    "python_requires": ">=3.11,<3.14",
    "py_modules": [
        "run_agent", "model_tools", "toolsets", "batch_runner",
        "trajectory_compressor", "toolset_distributions", "cli",
        "hercules_bootstrap", "hercules_constants", "hercules_state",
        "hercules_time", "hercules_logging", "utils", "mcp_serve"
    ],
    "packages": [
        "agent", "agent.consensus", "agent.transports",
        "tools", "hercules_cli", "gateway", "tui_gateway",
        "cron", "acp_adapter", "plugins", "providers"
    ],
    "install_requires": [
        "openai==2.24.0", "certifi==2026.5.20", "python-dotenv==1.2.2",
        "fire==0.7.1", "httpx[socks]==0.28.1", "rich==14.3.3",
        "tenacity==9.1.4", "pyyaml==6.0.3", "ruamel.yaml==0.18.17",
        "requests==2.33.0", "jinja2==3.1.6", "pydantic==2.13.4",
        "prompt_toolkit==3.0.52", "croniter==6.0.0", "packaging==26.0",
        "Markdown==3.10.2", "PyJWT[crypto]==2.13.0", "urllib3>=2.7.0,<3",
        "cryptography==46.0.7", "psutil==7.2.2", "websockets==15.0.1",
        "pathspec==1.1.1", "fastapi>=0.104.0,<1", "uvicorn[standard]>=0.24.0,<1",
        "python-multipart>=0.0.9,<1", "Pillow==12.2.0",
        "ptyprocess>=0.7.0,<1; sys_platform != 'win32'",
        "pywinpty>=2.0.0,<3; sys_platform == 'win32'",
        "concurrent-log-handler==0.9.29; sys_platform == 'win32'",
        "tzdata==2025.3; sys_platform == 'win32'",
    ],
    "extras_require": {
        "anthropic": ["anthropic==0.87.0"],
        "exa": ["exa-py==2.10.2"],
        "firecrawl": ["firecrawl-py==4.17.0"],
        "fal": ["fal-client==0.13.1"],
        "edge-tts": ["edge-tts==7.2.7"],
        "dev": ["debugpy==1.8.20", "pytest==9.0.2", "pytest-asyncio==1.3.0",
                "pytest-xdist==3.6.1", "mcp==1.26.0", "starlette==1.0.1",
                "ty==0.0.21", "ruff==0.15.10", "setuptools==81.0.0"],
        "mcp": ["mcp==1.26.0", "starlette==1.0.1"],
        "web": ["fastapi==0.133.1", "uvicorn[standard]==0.41.0",
                "starlette==1.0.1", "python-multipart==0.0.27"],
    },
    "entry_points": {
        "console_scripts": [
            "hercules=hercules_cli.main:main",
            "hercules-agent=run_agent:main",
            "hercules-acp=acp_adapter.entry:main",
        ],
    },
    "classifiers": [
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
    ],
}


def _source_tree_is_writable() -> bool:
    probe = REPO_ROOT / ".setuptools-write-probe"
    try:
        with probe.open("w", encoding="utf-8") as handle:
            handle.write("")
        probe.unlink()
    except OSError:
        try:
            probe.unlink(missing_ok=True)
        except OSError:
            pass
        return False
    return True


def _temporary_build_dir(kind: str) -> str:
    return tempfile.mkdtemp(prefix=f"hercules-agent-{kind}-")


def _would_write_under_source(path_value: str | None) -> bool:
    if path_value is None:
        return True
    path = Path(path_value)
    if not path.is_absolute():
        path = REPO_ROOT / path
    try:
        path.resolve().relative_to(REPO_ROOT)
    except ValueError:
        return False
    return True


class ReadOnlySourceBuild(_build):
    def finalize_options(self) -> None:
        if (
            not _source_tree_is_writable()
            and _would_write_under_source(self.build_base)
        ):
            self.build_base = _temporary_build_dir("build")
        super().finalize_options()


class ReadOnlySourceEggInfo(_egg_info):
    def finalize_options(self) -> None:
        if (
            not _source_tree_is_writable()
            and _would_write_under_source(self.egg_base)
        ):
            self.egg_base = _temporary_build_dir("egg-info")
        super().finalize_options()


def _data_file_tree(root_name: str) -> list[tuple[str, list[str]]]:
    root = REPO_ROOT / root_name
    grouped: defaultdict[str, list[str]] = defaultdict(list)
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel_path = path.relative_to(REPO_ROOT)
        grouped[str(rel_path.parent)].append(str(rel_path))
    return sorted(grouped.items())


# Build kwargs: use fallback metadata if pyproject.toml is PLACEHOLDER
setup_kwargs = {
    "cmdclass": {
        "build": ReadOnlySourceBuild,
        "egg_info": ReadOnlySourceEggInfo,
    },
    "data_files": [
        *_data_file_tree("skills"),
        *_data_file_tree("optional-skills"),
    ]
}

# In PLACEHOLDER mode, temporarily move pyproject.toml so setuptools doesn't try to parse it
# (setuptools.setup() tries to read pyproject.toml before our code runs)
placeholder_mode = _pyproject_is_placeholder()
pyproject_path = REPO_ROOT / "pyproject.toml"
pyproject_backup_path = REPO_ROOT / "pyproject.toml.placeholder"

try:
    if placeholder_mode:
        print("⚠️  pyproject.toml is PLACEHOLDER — using fallback metadata", file=sys.stderr)
        # Move PLACEHOLDER out of the way temporarily
        if pyproject_path.exists():
            pyproject_path.rename(pyproject_backup_path)
        # Provide fallback metadata
        setup_kwargs.update(PLACEHOLDER_METADATA)

    setup(**setup_kwargs)

finally:
    # Restore PLACEHOLDER if we moved it
    if placeholder_mode and pyproject_backup_path.exists():
        pyproject_backup_path.rename(pyproject_path)
