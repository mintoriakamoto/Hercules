# Changelog

All notable changes to Hercules Agent are documented here. This project
follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added — Multi-agent orchestration

- **Self-correcting delegation (`delegation.verify_repair_rounds`).** The
  adversarial verification wave already refuted bad subtask claims but only
  reported them. With repair rounds enabled (default 0 = off, max 3), a task
  the verifier refutes is handed to a repair child seeded with the refutation
  evidence, then re-verified — looping until the verdict flips to verified or
  the round budget is spent. The repaired outcome is adopted as the task's
  result. Off by default, so the verify wave is unchanged unless opted in.
- **Dependency-DAG delegation (`depends_on`).** A batched `delegate_task` task
  can now declare `depends_on=[indices]` to run only after those tasks finish,
  receiving each prerequisite's output injected into its goal. Producers feed
  consumers without hand-wiring; the scheduler bounds concurrency to
  `max_concurrent_children`, validates the graph is acyclic, and is
  deadlock-free. Tasks with no `depends_on` run flat and in parallel as before.

## [2026.7.29]

### Added — Providers ("log in like the app, not an API key")

- **Kimi: real in-app login.** Selecting Kimi in `hercules model` /
  `hercules setup` now runs a full OAuth 2.0 **Device Authorization Grant**
  (RFC 8628) — open `kimi.com`, enter the code, done — and persists the grant
  to Hercules' own auth store with automatic refresh. Previously the provider
  only *read* a separate Kimi Code CLI's credentials and silently bounced when
  none existed. An existing Kimi CLI session still works as a fallback, and the
  device endpoint is env-overridable (`KIMI_OAUTH_DEVICE_CODE_URL`).
- **Gemini "Login with Google"** (Code Assist) and **Kimi/Qwen reuse-CLI-creds**
  providers wired end-to-end across the registry, credential pool, setup flows,
  and runtime resolution.

### Fixed

- **Gemini "Login with Google" 404 on every request.** The Code Assist
  translating transport was installed only on the shared client, but the
  conversation loop rebuilds a fresh per-request client for each call — dropping
  the transport so requests hit `/v1internal/chat/completions`, which Google's
  frontend answers with an HTML `Error 404`. Code Assist client construction now
  lives at the single `create_openai_client` chokepoint (so every path carries
  the transport), and the per-request factory reuses the shared client to keep
  the once-per-session onboarding cache.
- **Gemini first-login failures.** `:onboardUser` is a long-running operation;
  Google provisions free-tier projects asynchronously. The handshake now polls
  until the operation completes (matching gemini-cli) instead of reading an
  empty project id and failing every subsequent request.

### Changed — Branding & docs

- **mintoriakamoto** vendor identity across installers, desktop metadata, and the
  CLI: the startup banner now renders a per-column true-color gold gradient
  with a TTY-gated reveal animation (`HERCULES_BANNER_ANIM=0` to disable;
  piped/CI output is unchanged). Product name and MIT/Nous derivation credit
  are unchanged.
- Swept `website/docs` of stale Nous Portal references (removed provider,
  dead links, `setup --portal`); OAuth logins and OpenRouter are presented
  neutrally.

### CI / Release

- **Desktop installers for all three platforms.** The Desktop Release workflow
  now also builds unsigned macOS (`.dmg`/`.zip`) and Windows (`.exe`/`.msi`)
  installers alongside Linux (`.AppImage`/`.deb`/`.rpm`).
- **PyPI publishing is manual-only** (`workflow_dispatch`); the fork
  distributes via GitHub Releases and the install scripts.
- **CodeQL moved to an advanced setup** with a repo config that excludes the
  one high-noise query (`py/clear-text-logging-sensitive-data`, agent debug
  logging); all other security queries remain enabled on push, PR, and weekly.

## [1.0.0] — Hercules

The **1.0 milestone**: a full rebrand to **Hercules**, removal of the Nous
provider, a self-sufficient cron system, and a memory system rebuilt into a
generative-agents-grade engine.

### Breaking

- **Rebrand Hermes → Hercules (no compatibility shims).** Every identifier,
  environment variable (`HERMES_*` → `HERCULES_*`), the config directory
  (`~/.hermes` → `~/.hercules`), module names, the `hercules` launcher, Docker
  services, the TUI package, and the `hercules-agent` package name were
  renamed. **Existing installs must migrate** their env vars and config
  directory; the `hermes` command no longer exists.
- **Removed the Nous Portal provider entirely** — its OAuth/device-code auth,
  credential pool, credits tracking, subscription/managed-tool gating, portal
  onboarding, and the `nous` provider option. The auxiliary-model fallback is
  now `OpenRouter → main`. Codex, xAI, Qwen, Anthropic, Gemini, OpenRouter,
  and Kimi/Moonshot are unaffected.

### Added — Memory system (the headline)

The holographic memory went from a keyword-matching fact store to a
three-layer, self-maintaining, belief-forming system:

- **Semantic retrieval.** Dense embeddings (any OpenAI-compatible endpoint,
  incl. local vLLM/Ollama) with a **union recall path** — facts whose *meaning*
  matches surface even with zero keyword overlap. Blended with FTS5, Jaccard,
  and HRR, weighted by trust, importance, and recency decay. Optional **HyDE**
  query rewriting.
- **Self-curation.** Typed memory (**profile** = always-injected/durable vs
  **episodic** = on-demand), **LLM-gated salience** (clean atomic facts, not
  raw turns), and **self-maintaining consolidation** — semantic dedup plus
  **supersede-on-contradiction** so the store stays coherent as reality changes.
- **Reflection.** Periodic synthesis of recent observations into higher-order
  **insights** promoted to durable profile memory, with **importance scoring**
  and **provenance** (`fact_sources` + a `why` tool) — "why do you believe
  that?" walks the evidence chain.
- **Graph reasoning.** Multi-hop associative recall over the fact↔entity graph
  ("what do I know about X and everything connected to X").
- All backends are pluggable, auto-enabling, graceful (clean fallback when
  off), and covered by deterministic tests.

### Added / Changed — Cron

- The **built-in in-process scheduler** is now the definitive Hercules cron
  provider (no external service). The Nous-mediated Chronos provider was
  retired; its useful half — an **authenticated inbound fire-webhook** (generic
  JWT verifier, `cron.fire.*` config) — was promoted to core so any external
  scheduler can trigger jobs.

### Fixed / Hardened

- Closed a CI merge-gate bypass (a failed classifier could report green) and a
  workflow script-injection sink; hardened `.gitignore` and credential logging.
- Preserve large-integer precision in tool-arg coercion (snowflake IDs no
  longer corrupted).
- Trajectory compressor: fixed compressible-region collapse, an `AsyncOpenAI`
  client leak, and a retry-count edge case.
- Browser: Chrome fallback now injects the sandbox bypass (worked around a
  dead-end in the default Docker deployment) and surfaces real errors.
- Gateway: background watcher tasks are tracked for GC-safety and clean
  shutdown; the cron-fire task is GC-safe.
- Memory: fixed a stale HRR bank corruption on category change and a
  LIKE-wildcard entity-resolution bug.

### Changed — Branding

- New **Aegean Teal / Laurel** theme across the web dashboard, desktop app, and
  installer, replacing the inherited "Nous Blue".
