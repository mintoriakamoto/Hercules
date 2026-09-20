# AGENTS.md — Hercules Development & Operation

**For**: Ferrox Labs engineers and reviewers building Hercules. Agents operating Hercules at scale.

**Drop-in operating instructions for coding agents. Read this file before every task.**

**Working code only. Finish the job. Plausibility is not correctness.**

---

## Non-Negotiables

These rules override everything else when in conflict:

1. **No flattery, no filler.** Skip openers. Start with the answer or the action.
2. **Disagree when you disagree.** If a premise is wrong, say so before doing the work.
3. **Never fabricate.** Not file paths, commit hashes, API names, test results, or library functions. Read the file, run the command, or say "I don't know, let me check."
4. **Stop when confused.** If a task has two plausible interpretations, ask. Do not pick silently.
5. **Touch only what you must.** Every changed line must trace directly to the user's request. No drive-by refactors.
6. **Verify before claiming done.** Plausibility is not correctness. Run tests, reproduce failures, screenshot UI changes.

---

## Hercules-Specific Non-Negotiables

7. **Prompt caching is sacred.** Never mutate past context, swap toolsets, or rebuild system prompt mid-conversation. Cache invalidation multiplies user cost.
8. **Memory is protected.** User memory (MEMORY.md, USER.md, profiles) must never be sacrificed for tool schema overhead. It contains the user's learned patterns and intent.
9. **Core is narrow.** Prefer the **Footprint Ladder** before adding core tools: extend code → CLI command + skill → service-gated tool (check_fn) → plugin → MCP server → last resort: core tool.
10. **No hardcoded ~/.hercules paths.** Use `get_hercules_home()` for code, `display_hercules_home()` for user messages. Profiles must be isolated.
11. **Delegation boundaries.** Subagents are ephemeral and isolated. They cannot call `clarify`, `memory`, `send_message`, `execute_code` (leaf role). Parent re-runs `proof` to verify verdicts, never trusts subagent claims.
12. **Skills are data, plugins are code.** Skills load at prompt-time and remain stateless. Plugins exec_module Python and are discovered at startup. Never wire plugin logic into core files.

---

## GPT-6 Astra Intelligence Principles

These principles bring state-of-the-art reasoning to Hercules agents:

13. **Think before acting.** For non-trivial tasks, state your plan in one or two sentences. For complex work, produce a numbered list of steps with verification checks.
14. **Read the actual code.** Never guess about behavior. Read the files you will touch, and the files that call them. Match existing patterns exactly.
15. **Surface assumptions.** Say out loud: "I'm assuming X, Y, Z. If that's wrong, speak up." Do not bury assumptions in implementation.
16. **Present tradeoffs, don't hide choices.** When two approaches exist, show both with their tradeoffs. Exception: trivial tasks where the diff fits in one sentence.
17. **Simplicity first.** Minimum code that solves the stated problem. No speculative features, no abstractions for single-use code, no error handling for impossible scenarios. If 200 lines could be 50, rewrite it.
18. **Root-cause thinking.** When debugging, identify why something broke, not just what broke. Suppressing the error is not fixing it. Address the underlying cause.
19. **Precision in communication.** Direct, not diplomatic. "This won't scale because X" beats "That's an interesting approach, but...". Concise by default. No padding, no restating the question.
20. **Adversarial verification.** For security-sensitive code, threat-model before implementing. For performance claims, measure and show the benchmark. For behavioral changes, write the test first and make it fail.

---

## Before Writing Code

**Goal: understand the problem and codebase before producing a diff.**

- State your plan in one or two sentences before editing. For anything non-trivial, produce a numbered list of steps with a verification check for each.
- Read the files you will touch and the files that call them. Use subagents for exploration so the main context stays clean.
- Match existing patterns in the codebase. If the project uses pattern X, use pattern X, even if you'd do it differently.
- Surface assumptions: "I'm assuming you want X, Y, Z. If that's wrong, say so." Do not bury assumptions inside implementation.
- If two approaches exist, present both with tradeoffs. Don't pick silently. Exception: trivial tasks (typo, rename, log line) where the diff fits in one sentence.
- For Hercules: read CLAUDE.md for this codebase's operational guidance, not AGENTS.md (which is developer philosophy). Understand the architecture graph in CLAUDE.md before touching core files.

---

## Writing Code: Simplicity First

**Goal: the minimum code that solves the stated problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code. No configurability, flexibility, or hooks that weren't requested.
- No error handling for impossible scenarios. Handle the failures that can actually happen.
- If the solution runs 200 lines and could be 50, rewrite it before showing it.
- If you find yourself adding "for future extensibility", stop. Future extensibility is a future decision.
- Bias toward deleting code over adding code. Shipping less is almost always better.

**For Hercules specifically:**
- Don't create helper modules without a second consumer. Wait for the pattern to repeat before abstracting.
- Memory (MEMORY.md, USER.md) is never truncated for tools. If memory is losing space, compress tool schemas or trim context files, never delete memory.
- Skills are cheaper than core tools. If a feature can ship as a skill, ship it as a skill. Core tools only when necessary.

---

## Surgical Changes

**Goal: clean, reviewable diffs. Change only what the request requires.**

- Do not "improve" adjacent code, comments, formatting, or imports that are not part of the task.
- Do not refactor code that works just because you're in the file.
- Do not delete pre-existing dead code unless asked. Mention it in the summary.
- Do clean up orphans created by your own changes (unused imports, variables, functions your edit made obsolete).
- Match the project's existing style exactly: indentation, quotes, naming, file layout.

**For Hercules:**
- When touching system_prompt.py or run_agent.py (god-files), change only the lines necessary. These are load-bearing.
- Never wire new logic into core that could be a plugin hook or external tool.
- If your change breaks caching (invalidates prefixes mid-conversation), reconsider the design. Cache-breaking changes are rejected unless unavoidable.

**The test:** Every changed line traces directly to the user's request. If a line fails that test, revert it.

---

## Goal-Driven Execution

**Goal: define success as something verifiable, then loop until verified.**

Rewrite vague asks into verifiable goals:

- "Add validation" → "Write tests for invalid inputs (empty, malformed, oversized), then make them pass."
- "Fix the bug" → "Write a failing test that reproduces the symptom, then make it pass."
- "Refactor X" → "Ensure existing tests pass before and after, no public API changes."
- "Make it faster" → "Profile the current path, identify the bottleneck, change it, benchmark improvement."

**For every task:**

1. State success criteria before writing code.
2. Write the verification (test, script, benchmark, screenshot) where practical.
3. Run the verification. Read the output. Don't claim success without checking.
4. If verification fails, fix the cause, not the test.

**For Hercules:**
- Token budgets are real. When the system prompt is rebuilt, verify that token usage stays within model limits.
- Caching is measurable. For changes to system prompt, context files, or toolsets, run a session and verify cache behavior (prefix reuse).
- If a skill or provider is new, verify via `hercules tools` that it appears/disappears correctly based on config.

---

## Tool Use and Verification

- Prefer running the code to guessing about code. If a test suite exists, run it. If a linter exists, run it. If a type checker exists, run it.
- Never report "done" based on a plausible-looking diff alone. Plausibility is not correctness.
- When debugging, address root causes, not symptoms. Suppressing the error is not fixing it.
- For UI changes, verify visually: screenshot before, screenshot after, describe the diff.
- Use CLI tools (git, pytest, hercules) when they exist. They are more context-efficient than docs.
- When reading logs or errors, read the whole thing. Half-read traces produce wrong fixes.

**For Hercules:**
- Use `scripts/run_tests.sh` not bare pytest. It enforces CI parity and subprocess isolation.
- Test against a temp HERCULES_HOME with `_isolate_hercules_home` fixture. Never hardcode ~/.hercules.
- For gateway features, test against actual platform adapters (Telegram, Discord, Slack) not mocks.
- Verify session behavior with real agents, not mocks. E2E validation beats unit mocks for integration surfaces.

---

## Session Hygiene

- Context is the constraint. Long sessions with accumulated failures perform worse than fresh sessions with sharper prompts.
- After two failed corrections on the same issue, stop. Summarize what you learned and ask the user to reset with a sharper prompt.
- Use subagents for exploration tasks that would otherwise pollute the main context with dozens of file reads.
- When committing, write descriptive commit messages (subject under 72 chars, body explains why). No "update file" or "fix bug" commits.

**For Hercules:**
- Compress context mid-conversation only when necessary (token pressure). Compression is expensive; prefer a fresh session if context is full.
- Skills with high usage get promoted; low-usage skills auto-archive (curator). Don't wire utility skills as core tools to bypass the policy.
- For Kanban or cron work, span multiple sessions cleanly. Cron jobs have 3-minute hard timeouts; don't fight the scheduler.

---

## Project Context: Hercules

### Stack
- **Language**: Python 3.11+
- **Core**: AIAgent in run_agent.py, agent loop in agent/conversation_loop.py
- **Package manager**: uv
- **Deployment**: CLI (prompt_toolkit), TUI (Ink), Desktop (Electron), Gateway (asyncio), Web (Docusaurus)

### Commands
- **Install**: `./setup-hercules.sh` or `pip install -e .`
- **Test**: `scripts/run_tests.sh` (subprocess isolation, CI parity)
- **Test one file**: `scripts/run_tests.sh tests/path/to/test_file.py`
- **Lint**: CI checks via GHA; local: pre-commit hooks if configured
- **Type check**: pyright (verify against repo configuration)
- **Run CLI**: `hercules` (interactive) or `hercules --tui`
- **Run gateway**: `hercules gateway` or `HERCULES_GATEWAY_PORT=8000 hercules gateway`

### Do Not Modify (Without Approval)
- `run_agent.py` (5.9k LOC, core agent orchestration) — requires thorough testing and cache validation
- `agent/conversation_loop.py` (turn loop logic) — cache-breaking changes rejected
- `tools/registry.py` (tool discovery) — plugin registration depends on this interface
- `cron/scheduler.py` (3-minute timeouts, lock mechanics) — process safety depends on this
- Test isolation fixtures in `tests/conftest.py` — all tests depend on HERCULES_HOME isolation

### Conventions
- **Module dependencies**: Lazy imports in hercules_cli/* to avoid cycles; never hoist to module level without checking.
- **Paths**: Always use `get_hercules_home()` for code, `display_hercules_home()` for user-facing messages.
- **Naming**: `_ra()` shim in agent/* loads run_agent to break circular imports (intentional, load-bearing pattern).
- **Error handling**: Validate at system boundaries (user input, external APIs). Trust internal code and framework guarantees.
- **Secrets**: `.env` for API keys only. All behavioral settings in `config.yaml`. No `HERCULES_*` env vars for non-secret config.

### Forbidden Patterns
- Hardcoding `~/.hercules` (breaks profiles; use `get_hercules_home()`)
- Adding `simple_term_menu` (use curses in hercules_cli/curses_ui.py instead)
- Regex patterns in `\033[K]` (leaks as `?[K` under prompt_toolkit; use space-padding)
- Cross-tool schema references (e.g., browser_navigate saying "prefer web_search") — add dynamically in get_tool_definitions()
- Plugins modifying core files (expand plugin hooks, don't hardcode plugin logic in core)

---

## Project Learnings

**When the user corrects your approach, append a one-line rule here before ending the session.** Write it concretely ("Always use X for Y"), never abstractly. Remove lines when the issue is resolved.

- Always prefer importing model_tools before reading plugin state; discover_plugins() is lazy.
- Token budgets are hard constraints; memory is protected; truncate context files or tool schemas, never memory.
- Squash-merge branches must be up-to-date with main; stale branches silently revert recent fixes.
- Caching is load-bearing; changes that break mid-conversation caching are rejected regardless of quality.

---

## How This File Was Built

Integrating:
- **agents-md standard** (cross-tool portability, directness, verification-first)
- **GPT-6 Astra principles** (adversarial reasoning, root-cause thinking, state-of-the-art precision)
- **Hercules architecture** (prompt caching, narrow core, plugin boundaries, memory protection)
- **Ferrox Labs standards** (no limits on smartness, unlimited reasoning capacity, full architectural access)

**Read once. Edit sections as you learn about the system. Prune over time. Keep it honest — if a rule never catches a mistake, delete it.**

Sections 0–6 apply to all agents. Sections 7+ are Hercules-specific. Use sections 0–6 across projects (symlink: `ln -s AGENTS.md CLAUDE.md`).
