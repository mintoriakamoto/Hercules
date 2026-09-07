# Hercules Roadmap

> **Status:** This document describes direction and intent, not commitments.
> Dates and features are aspirational and will change. Anything marked
> **Done** is present in the repository today and can be verified in the code;
> everything else is planned or exploratory.

---

## Vision

Hercules is a self-improving AI agent. The goal is an agent that learns from
use, remembers across sessions, runs wherever you want it to, and never locks
you into a single model, platform, or vendor.

Three principles drive the roadmap:

### 1. Intelligence through learning

Most agents are stateless — they answer the current question and forget the
context. Hercules is built around a closed learning loop: it creates skills
from experience, improves them during use, persists knowledge deliberately,
and searches its own past conversations.

### 2. Autonomy and portability

You choose the model, the host, and the storage. Switching providers is a
config change, not a migration. Your conversations are yours — exportable and
deletable on demand.

### 3. Present where you work

One agent, reachable from the terminal, Telegram, Discord, Slack, WhatsApp,
and Signal, with conversation continuity across all of them.

---

## Done

These are implemented and verifiable in the repository:

- **Structured error handling** — typed exception hierarchy with severity
  levels (`agent/error_handling_standards.py`)
- **Error recovery patterns** — retry with exponential backoff, circuit
  breaker, fallback chains (`agent/error_recovery_patterns.py`)
- **Centralized input validation** — validators guarding against path
  traversal, command injection, and type confusion (`agent/input_validation.py`)
- **Production pre-flight validator** — startup checks for imports, file
  access, and environment (`agent/production_validator.py`)
- **Multi-platform gateway** — Telegram, Discord, Slack, WhatsApp, Signal, CLI
- **Six terminal backends** — local, Docker, SSH, Singularity, Modal, Daytona
- **Learning loop** — skill creation from experience, self-improvement during
  use, FTS5 session search, Honcho user modeling
- **Scheduled automations** — built-in cron with delivery to any platform
- **Hardware tuning guide** — dual-GPU and multi-core configuration
  (`docs/HARDWARE_CONFIGURATION.md`)

---

## Near term

### Memory and recall
- Semantic search over past sessions alongside the existing FTS5 index
- Better cross-session context compression
- More reliable memory persistence nudges

### Skills
- Higher-quality autonomous skill generation from task trajectories
- Skill performance feedback so weak skills get revised rather than reused
- Broader compatibility with the [agentskills.io](https://agentskills.io) standard

### Model routing
- Automatic model selection by task type
- Cost-aware routing across configured providers
- Graceful degradation when a provider is unavailable

---

## Medium term

### Reach
- Web console for conversation history, search, and settings
- Native mobile clients
- Real-time sync so a session started on one surface continues on another

### Multimodal
- Image understanding and OCR in the tool loop
- Improved voice transcription and voice conversation continuity
- Document ingestion as a first-class input

### Collaboration
- Shared agent instances with role-based access
- Team workspaces grouping conversations, skills, and automations
- Audit logging for shared deployments

---

## Exploratory

Ideas under consideration. No timeline, and some will be dropped.

- Vector store integration as an alternative memory backend
- Local fine-tuning for per-user model adaptation
- Federated learning so model improvements do not require sharing raw data
- Multi-agent coordination beyond the current subagent spawning
- Knowledge-graph reasoning over accumulated memory
- Deeper trajectory compression for training tool-calling models

---

## Non-goals

Stating these explicitly so the scope stays honest:

- **Not** a hosted-only product — self-hosting stays a first-class path
- **Not** locked to one model vendor
- **Not** a closed ecosystem — skills and plugins stay portable
- **Not** collecting user conversations for training

---

## Quality bar

Targets the project holds itself to, measured in CI and production use:

| Area | Target |
|---|---|
| Unhandled exceptions | Zero in critical paths |
| Test coverage | High coverage on error handling, validation, gateway |
| Startup validation | Pre-flight checks pass before any service starts |
| Dependency security | Lockfile hash verification, scanned in CI |
| Input validation | All external input passes centralized validators |

---

## Contributing to the roadmap

The roadmap is shaped by what people actually need.

- **Propose something:** open a [discussion](https://github.com/mintoriakamoto/Hercules/discussions)
- **Report a gap:** open an [issue](https://github.com/mintoriakamoto/Hercules/issues)
- **Build something:** see [CONTRIBUTING.md](CONTRIBUTING.md)

Items move from *Exploratory* to *Near term* when someone commits to building
them — including you.
