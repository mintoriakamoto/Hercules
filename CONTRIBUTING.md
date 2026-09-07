# Contributing to Hercules

Thank you for your interest in contributing to Hercules! This document provides guidelines and instructions for contributing to the project.

## Code of Conduct

This project adheres to the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

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
- Use `ruff` for linting
- Add type hints
- Follow PEP 8
- Target Python 3.11+

**TypeScript:**
- Use `eslint`
- Write tests with Jest
- Maintain type safety

### 4. Testing

```bash
pytest                    # Run all tests
pytest --cov=hercules_cli # With coverage
ruff check .              # Lint
mypy .                    # Type check
```

Requirements:
- ✓ All tests pass
- ✓ Minimum 80% coverage for new code
- ✓ Deterministic tests
- ✓ No linting errors

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
