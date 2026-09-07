# Hercules Agent Architecture

This document provides a high-level overview of Hercules Agent's architecture, key components, and their interactions.

## System Overview

Hercules Agent is a self-improving AI agent that can be run anywhere — local machine, VPS, cloud VM, or serverless infrastructure. It features:

- **Modular plugin system** for extensibility
- **Multiple platform adapters** (CLI, TUI, Telegram, Discord, Slack, etc.)
- **Model provider abstraction** for switching between LLM providers
- **Autonomous skill creation and improvement**
- **Scheduled automations** with cron support
- **Multiple terminal backends** (local, Docker, SSH, Singularity, Modal, Daytona)

## Directory Structure

```
Hercules/
├── acp_registry/              # ACP (Agent Client Protocol) manifest
├── agent/                     # Core agent implementation
├── apps/                      # Web and desktop applications
├── gateway/                   # Platform adapters (Telegram, Discord, Slack, etc.)
│   └── platforms/             # Individual platform integrations
├── hercules_cli/              # CLI interface and subcommands
│   ├── subcommands/           # Individual CLI commands (doctor, update, etc.)
│   └── main.py                # CLI entry point
├── plugins/                   # Plugin system
│   └── model-providers/       # LLM provider implementations
├── providers/                 # Legacy provider system
├── optional-mcps/             # Optional MCP (Model Context Protocol) servers
├── optional-skills/           # Optional skill definitions
├── skills/                    # Core skill system
├── cron/                      # Cron scheduler for automations
├── web/                       # Web dashboard
├── ui-tui/                    # Terminal user interface (TUI)
├── docker/                    # Docker configuration
├── scripts/                   # Utility scripts
├── tests/                     # Test suite
├── docs/                      # Documentation
└── .github/                   # GitHub configuration
    ├── workflows/             # CI/CD pipelines
    └── ISSUE_TEMPLATE/        # Issue templates
```

## Core Components

### 1. Agent Core (`agent/`)

The heart of Hercules — the main agent loop, message handling, and state management.

**Key Files:**
- `agent.py` - Main agent class
- `context.py` - Context management and session handling
- `memory.py` - Memory and conversation history
- `tools.py` - Tool registration and execution

**Responsibilities:**
- Process user input and maintain conversation context
- Dispatch work to tools and external services
- Manage approval gates and output redaction
- Coordinate with plugins and skills

### 2. CLI (`hercules_cli/`)

Command-line interface for local interaction and management.

**Key Subcommands:**
- `doctor` - Diagnose configuration and connectivity
- `update` - Update Hercules from GitHub
- `config` - Manage configuration
- `skill` - Manage skills
- `model` - Switch between model providers
- `run` - Execute agent in interactive mode

**Architecture:**
- Uses argparse for command parsing
- Handler injection pattern to avoid circular dependencies
- Modular subcommand builders in `subcommands/`

### 3. Gateway (`gateway/`)

Bridges between user platforms (Telegram, Discord, Slack, etc.) and the agent core.

**Key Components:**
- Platform adapters in `gateway/platforms/`
- Message routing and formatting
- User session management
- Cross-platform conversation continuity

**Supported Platforms:**
- CLI (local terminal)
- TUI (Terminal User Interface)
- Telegram
- Discord
- Slack
- WhatsApp
- Signal
- Email
- SMS
- Custom HTTP API

### 4. Plugin System (`plugins/`)

Extensibility mechanism for adding new providers, tools, and features.

**Key Features:**
- Dynamic plugin discovery and loading
- Model provider plugins in `plugins/model-providers/`
- Provider registration and initialization
- Environment-based configuration

**Model Providers:**
- TENSELERATE (local llama.cpp via llama-server)
- Anthropic (Claude models)
- OpenAI (GPT models)
- OpenRouter (multi-model aggregator)
- Custom/local endpoints
- And many others via plugin system

### 5. Skills System (`skills/`, `optional-skills/`)

Autonomous skills that the agent creates, maintains, and improves.

**Features:**
- Skill creation from experience
- Skill improvement during use
- Skill versioning and persistence
- FTS5 full-text search across skills
- Honcho user modeling integration

**Skill Lifecycle:**
1. Agent encounters complex task
2. Analyzes pattern and creates skill template
3. Skill is curated and refined by agent
4. Skill self-improves through usage
5. Agent persists improvements to disk

### 6. Model Providers (`plugins/model-providers/`)

Abstraction layer for different LLM providers.

**Provider Structure:**

Each provider includes:
- `ProviderProfile` class defining capabilities
- Authentication configuration (API key, OAuth, etc.)
- Request/response handling
- Model listing and metadata
- Health checks and error handling

**Key Methods:**
- `fetch_models()` - Get available models
- `build_api_kwargs_extras()` - Transform requests for provider API
- `validate_credentials()` - Check authentication

**Example: TENSELERATE**
```python
tenselerate = TenselerateProfile(
    name="tenselerate",
    display_name="TENSELERATE",
    base_url="http://127.0.0.1:8080/v1",
    models_url="http://127.0.0.1:8080/v1/models",
    auth_type="api_key",
    env_vars=("TENSELERATE_API_KEY",),
    default_max_tokens=65536,
)
```

### 7. Cron Scheduler (`cron/`)

Scheduled automations running in background.

**Features:**
- Natural language cron definitions
- Delivery to any platform (Telegram, email, etc.)
- Error handling and retry logic
- Audit logging

### 8. Terminal Backends

Pluggable execution targets for shell commands:

1. **Local** - Direct host execution
2. **Docker** - Container-based isolation
3. **SSH** - Remote host execution
4. **Singularity** - HPC container support
5. **Modal** - Serverless functions
6. **Daytona** - Persistent serverless environments

## Data Flow

### Typical Interaction Flow

```
User Input
    ↓
Gateway/Platform Adapter
    ↓
Agent Core (Message Processing)
    ↓
Context Management & History
    ↓
Tool Dispatch & Execution
    ├→ File Operations
    ├→ Terminal Commands
    ├→ External APIs
    └→ Skills & Plugins
    ↓
LLM Provider (Model Call)
    ↓
Output Processing
    ├→ Redaction
    ├→ Formatting
    └→ Approval Gate (if needed)
    ↓
Gateway Response
    ↓
User Platform
```

### Skill Creation Flow

```
Complex Task Encountered
    ↓
Agent Analysis & Pattern Recognition
    ↓
Skill Template Generation
    ↓
User Approval/Curation
    ↓
Skill Implementation
    ↓
Testing & Validation
    ↓
Persistence to Disk
    ↓
Usage Tracking & Improvement
```

## Configuration

### Environment Variables

**Provider Credentials:**
- `ANTHROPIC_API_KEY` - Anthropic API key
- `OPENAI_API_KEY` - OpenAI API key
- `TENSELERATE_API_KEY` - TENSELERATE local API key

**Gateway Configuration:**
- `HERCULES_GATEWAY_TELEGRAM_TOKEN` - Telegram bot token
- `HERCULES_GATEWAY_DISCORD_TOKEN` - Discord bot token
- `HERCULES_GATEWAY_SLACK_TOKEN` - Slack bot token

**Agent Configuration:**
- `HERCULES_HOME` - Agent home directory (default: `~/.hercules`)
- `HERCULES_MODEL` - Default model provider
- `HERCULES_BACKEND` - Terminal backend (local/docker/ssh/etc.)

### Configuration Files

**Location:** `~/.hercules/config.yaml` (or `HERCULES_HOME/config.yaml`)

**Sections:**
- `agent` - Agent behavior settings
- `providers` - Model provider configuration
- `gateway` - Platform adapter settings
- `terminal` - Backend configuration
- `memory` - Memory and history settings

## Key Design Patterns

### 1. Provider Registration

Providers register themselves at import time:

```python
from providers import register_provider

register_provider(tenselerate)
```

This allows dynamic provider discovery and configuration validation.

### 2. Handler Injection

CLI subcommands use handler injection to avoid circular dependencies:

```python
def build_doctor_parser(subparsers, *, cmd_doctor: Callable) -> None:
    doctor_parser = subparsers.add_parser("doctor")
    doctor_parser.set_defaults(func=cmd_doctor)
```

### 3. Tool Dispatch

Tools are dispatched through a unified interface:

```python
# In agent core
result = tool.execute(**kwargs)
```

Each tool handles:
- Argument validation
- Execution
- Error handling
- Result formatting

### 4. Plugin Loading

Plugins are discovered and loaded dynamically:

```python
# On startup
import importlib
plugin = importlib.import_module(f"plugins.{name}")
plugin.initialize()
```

## Security Model

See [SECURITY.md](../SECURITY.md) for comprehensive security documentation.

**Key Points:**
- OS-level isolation is the security boundary
- In-process heuristics (approval gate, redaction) are not boundaries
- Provider credentials are environment-variable based
- Third-party skills/plugins require operator review

## Testing

**Test Structure:**
- `tests/` - Unit and integration tests
- Test organization mirrors source structure
- Pytest with parallel execution (8 slices)
- Minimum 80% code coverage for new code

**Running Tests:**
```bash
pytest                              # All tests
pytest --cov=hercules_cli           # With coverage
pytest -k "test_doctor"             # Specific test
pytest -x                           # Stop on first failure
```

## CI/CD Pipeline

**GitHub Actions Workflows:**

1. **Code Quality**
   - Ruff linting and formatting
   - MyPy type checking
   - CodeQL security analysis

2. **Testing**
   - Unit tests across Python versions
   - Integration tests
   - Coverage reports

3. **Build & Release**
   - Package building (wheel/sdist)
   - Docker image building
   - Release asset creation

4. **Deployment**
   - PyPI package publishing
   - Docker image pushing
   - GitHub release creation

## Performance Considerations

### Model Provider Selection

- **Local (TENSELERATE)** - Low latency, no network overhead
- **Anthropic/OpenAI** - Higher latency, managed service benefits
- **OpenRouter** - Model selection flexibility

### Terminal Backend

- **Local** - Fastest, least isolated
- **Docker** - Moderate overhead, good isolation
- **Serverless** - Cold start overhead, scales infinitely

### Memory Management

- Conversation history is truncated for long sessions
- Skills cache important patterns
- Regular cleanup of temporary artifacts

## Extension Points

### Adding a New Platform Adapter

1. Create `gateway/platforms/newplatform.py`
2. Implement `PlatformAdapter` interface
3. Register in `gateway/__init__.py`
4. Add configuration schema
5. Add tests

### Adding a Model Provider

1. Create `plugins/model-providers/newprovider/__init__.py`
2. Extend `ProviderProfile` class
3. Implement required methods
4. Add environment variable requirements
5. Register provider at module level
6. Add tests

### Adding a New CLI Command

1. Create `hercules_cli/subcommands/newcommand.py`
2. Implement `build_newcommand_parser()` function
3. Create handler function
4. Register in `hercules_cli/main.py`
5. Add help text and argument definitions
6. Add tests

## Future Improvements

See GitHub issues and project board for planned enhancements.

## Related Documentation

- [CONTRIBUTING.md](../CONTRIBUTING.md) - Contribution guidelines
- [SECURITY.md](../SECURITY.md) - Security policy and trust model
- [Session Lifecycle](./session-lifecycle.md) - Session management
- [Relay Connector Contract](./relay-connector-contract.md) - Gateway protocol

## Questions?

- **Documentation** - See [docs/](.)
- **Issues** - [GitHub Issues](https://github.com/mintoriakamoto/Hercules/issues)
- **Discussions** - [GitHub Discussions](https://github.com/mintoriakamoto/Hercules/discussions)
