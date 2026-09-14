# Contributing to Hercules

Thank you for your interest in contributing! This document provides practical guidelines for the
contribution workflow. **Before you start coding, read [`AGENTS.md`](./AGENTS.md)** — it explains
the design philosophy, contribution rubric, and what we do/don't want. This guide assumes you've
understood that context.

## Code of Conduct

This project adheres to the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## Documentation Map

Before contributing, know which document to read for what:

| Document | Purpose | Read when you... |
|----------|---------|------------------|
| [`AGENTS.md`](./AGENTS.md) (root) | Design philosophy, contribution rubric, tech architecture | Planning a feature or fixing a bug; reviewing PRs |
| [`CONTRIBUTING.md`](./CONTRIBUTING.md) (this file) | Practical workflow, testing, code quality | Ready to start coding; need setup/build instructions |
| [`apps/desktop/AGENTS.md`](./apps/desktop/AGENTS.md) | Desktop app architecture and invariants | Building the Electron app; changing state, routing, or UI patterns |
| [`apps/desktop/DESIGN.md`](./apps/desktop/DESIGN.md) | Visual design system, components, tokens | Adding UI components or changing styles |

---

## Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+
- Docker (optional)
- Git

### Development Setup

```bash
git clone https://github.com/mintoriakamoto/Hercules.git
cd Hercules
uv pip install -e ".[dev]"
npm install
pre-commit install
```

## Development Workflow

### 1. Create a Branch
```bash
git checkout -b feat/your-feature-name
```

Branch naming: `feat/`, `fix/`, `docs/`, `refactor/`, `test/`, `chore/`

### 2. Make Changes
- Write clear commit messages
- Keep commits focused
- Reference issues: `fixes #123`
- Add tests for new code
- Update docs

### 3. Code Quality

**Python:**
- `ruff check .` must pass. Only the rules in `pyproject.toml`
  `[tool.ruff.lint] select` are enforced (currently `PLW1514`: every
  text-mode `open()` / `read_text()` / `write_text()` needs an explicit
  `encoding=`). No formatter and no `mypy` run in CI.
- `python scripts/check-windows-footguns.py --all` must pass (Windows-unsafe
  primitives such as `os.killpg`, `os.setsid`, bare `signal.SIGKILL`).
- CI also posts an advisory ruff + `ty` diff against the target branch
  (`scripts/lint_diff.py`). It never fails the build; treat new diagnostics
  as review feedback.
- Add type hints
- Target Python 3.11+

**TypeScript:**
- Use `eslint`
- Write tests with Jest
- Maintain type safety (`npm run --prefix <package> typecheck` is what CI runs)

### 4. Testing

```bash
scripts/run_tests.sh                          # Full suite, as CI runs it
scripts/run_tests.sh tests/agent/             # One directory
scripts/run_tests.sh tests/agent/test_foo.py  # One file
ruff check .                                  # Lint (blocking in CI)
python scripts/check-windows-footguns.py --all # Windows footguns (blocking in CI)
```

Use `scripts/run_tests.sh`, not a bare `pytest tests/<dir>`. It runs each
test file in its own subprocess, which is how CI runs them; a directory-level
`pytest` shares module state across files and produces cross-test-pollution
failures that do not reproduce in isolation (see `CLAUDE.md`, "Running
tests"). CI installs `--extra all --extra dev`; tests for optional
integrations that fail locally with `FeatureUnavailable` are not regressions.

Requirements:
- ✓ All tests pass
- ✓ Minimum 80% coverage for new code
- ✓ Deterministic tests
- ✓ `ruff check .` and the Windows footgun checker pass

### 5. Commit & Push

```bash
git add .
git commit -m "feat: add new feature

Detailed description of changes.
Fixes #123"
git push -u origin feat/your-feature-name
```

### 6. Open a Pull Request

1. Fill out PR template completely
2. Submit as draft initially
3. Ensure all checks pass
4. Request review from maintainers

**PR Requirements:**
- ✓ All CI checks pass
- ✓ At least one maintainer approval
- ✓ No merge conflicts
- ✓ Referenced issues
- ✓ Tests included
- ✓ Documentation updated

## Reporting Issues

### Bug Reports
Include:
- Python/Node.js version
- OS and version
- Steps to reproduce
- Expected vs actual behavior
- Error messages/logs
- Minimal reproducible example

### Feature Requests
Include:
- Use case and motivation
- Proposed behavior
- Example usage
- Alternative approaches considered

### Security Issues
**Do not open public issues for security vulnerabilities.**

Email: security@mintoriakamoto.com

See [SECURITY.md](SECURITY.md) for details.

## Documentation

- Document public APIs with docstrings
- Add usage examples for features
- Update README.md for behavior changes
- Update CHANGELOG.md
- Update architecture docs if needed

## Project Structure

```
Hercules/
├── acp_registry/        # ACP manifest
├── docs/                # Documentation
├── hercules_cli/        # CLI implementation
├── plugins/             # Plugin system
├── optional-skills/     # Skill definitions
├── tests/               # Test suite
├── apps/                # Web/desktop apps
├── scripts/             # Utility scripts
└── .github/workflows/   # CI/CD
```

## Questions?

- **Documentation**: See [docs/](docs/)
- **Issues**: [GitHub Issues](https://github.com/mintoriakamoto/Hercules/issues)
- **Discussions**: [GitHub Discussions](https://github.com/mintoriakamoto/Hercules/discussions)
- **Email**: dev@mintoriakamoto.com

## License

By contributing, you agree your contributions will be licensed under the MIT License.

---

Thank you for contributing to Hercules! 🚀
