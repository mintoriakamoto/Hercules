# Prompt Composition & Sizing in Hercules

Hercules builds your system prompt once per session and caches it to optimize token usage. Understand how it's composed, measure its size, and optimize it for your workflow.

---

## System Prompt Architecture

The system prompt is built from **three tiers**, joined with line breaks:

### 1. Stable Tier (Cached, Never Rebuilt)
This tier is stable for the lifetime of your session:

- **Agent Identity** — `SOUL.md` from `~/.hercules/SOUL.md`, or `DEFAULT_SOUL_MD` if missing
- **Help Guidance** — Pointer to Hercules documentation
- **Task Completion Guidance** — "Finish the job. Don't fabricate output."
- **Parallel Tool Call Guidance** — "Batch independent calls into one turn"
- **Tool-Specific Guidance** — Only injected if those tools are loaded:
  - `MEMORY_GUIDANCE` (if `memory` tool is present)
  - `SKILLS_GUIDANCE` (if skill tools are present)
  - `SESSION_SEARCH_GUIDANCE` (if `session_search` is present)
  - `KANBAN_GUIDANCE` (if `kanban_show` is present)
- **Computer-Use Guidance** — Platform-specific (only if `computer_use` tool is loaded)
- **Tool-Use Enforcement** — Model-family specific (GPT, Gemini, Grok, etc.)
- **Environment Hints** — WSL, Termux, Python state (no token cost when clean)
- **Coding Posture** — Git workspace snapshot, refactoring discipline
- **Skills Index** — Available skills and descriptions (largest single block when many skills installed)
- **Platform Hints** — Per-platform guidance (Slack, Discord, Telegram, etc.)

### 2. Context Tier (Session-Stable)
This tier is stable within a session but may change between sessions:

- **AGENTS.md** — Project-specific guidance (from working directory)
- **CLAUDE.md / claude.md** — Codebase operational guidance (from working directory)
- **.cursorrules** — Cursor/IDE conventions (from working directory)
- **.hercules.md / HERCULES.md** — Git-root project guidance (walks up to git root)

### 3. Volatile Tier (Per-Turn)
This tier changes on every message and is never cached:

- **User Profile** — `USER.md` (if present in `~/.hercules/profiles/<active>/`)
- **Memory Snapshot** — Recent memory entries (if memory tool is enabled)
- **External Memory Provider Block** — For integration services
- **Metadata Line** — Timestamp, session ID, model name, provider

---

## Measuring Prompt Size

Use the `hercules prompt-size` command to see exactly where your token budget goes:

```bash
hercules prompt-size
```

**Example output:**

```
Prompt-size breakdown (platform=cli, model=unset)

  System prompt total :   25,039 B  (24.5 KB, 24,921 chars)

  Major blocks:
    skills index       :        0 B  (0.0 KB)
    memory             :        0 B  (0.0 KB)
    user profile       :        0 B  (0.0 KB)

  Prompt tiers:
    stable (identity/guidance/skills)   :   15,926 B  (15.6 KB)
    context (AGENTS.md/cwd files)       :    9,058 B  (8.8 KB)
    volatile (memory/profile/timestamp) :       51 B  (0.0 KB)

  Tool schemas         :   67,366 B  (65.8 KB, 35 tools)
```

### Interpreting the Output

- **System prompt total** — Your fixed prompt budget (stable + context). This is sent on every API call.
- **Skills index** — Size of the `<available_skills>` block. Largest contributor when many skills are installed.
- **Memory** — Size of memory snapshot in the volatile tier.
- **User profile** — Size of your USER.md.
- **Prompt tiers** — Breakdown by stability (stable tiers are cached; volatile is per-turn).
- **Tool schemas** — JSON size of all tool definitions. Sent on every call alongside the system prompt.

**Total token cost per turn:**
```
System prompt (KB) + Tool schemas (KB) + Message history + Your turn
```

The system prompt and tool schemas are **fixed** — they're the same on every turn. Focus optimization on:
1. Skills index (disable unused skills)
2. Tool schema size (disable unused toolsets)
3. Memory (archive old memory entries)

---

## Customizing Your Prompt

### 1. Agent Identity: Edit SOUL.md

The most important file. Define your agent's persona, work ethic, and style.

```bash
mkdir -p ~/.hercules
cat > ~/.hercules/SOUL.md << 'EOF'
# Hercules Agent Identity

You are Hercules Agent, the user's own agent.
You are direct, autonomous, and results-driven.

## Work Ethic

Think before acting. Read the actual code.
Prefer measurable improvements. Verify before claiming done.
Simplicity first. Address root causes.

...
EOF
```

See [`soul-md-template.md`](./soul-md-template.md) for a full template.

### 2. Project-Specific Guidance: AGENTS.md

Place in your working directory (project root):

```bash
cat > AGENTS.md << 'EOF'
# Project-Specific Guidance

This project uses:
- Python 3.11+
- pytest for tests
- uv for dependency management

Guidelines:
- Always run `scripts/run_tests.sh` after changes
- Match existing code patterns
- No breaking API changes without discussion
EOF
```

### 3. Optimize Skills

Check which skills are installed and their size:

```bash
hercules skills list
```

Disable unused skills in `~/.hercules/config.yaml`:

```yaml
agent:
  disabled_toolsets:
    - creativity
    - research
    - unused-skill-name
```

Re-measure:

```bash
hercules prompt-size
```

### 4. Optimize Tool Schemas

Disable unused toolsets:

```yaml
agent:
  disabled_toolsets:
    - browser_tools
    - network_tools
```

### 5. Monitor Token Usage

Before and after changes, run `prompt-size`:

```bash
# Before optimization
hercules prompt-size > before.txt

# Make changes (disable skills, etc.)

# After optimization
hercules prompt-size > after.txt

# Compare
diff before.txt after.txt
```

---

## The Three Tiers Explained

### Why Three Tiers?

**Prompt caching** — Hercules uses upstream prefix caching to reduce token cost. Once a prompt is built, the stable tier is cached and reused on every turn. Only the volatile tier (memory, timestamp) is sent fresh on each call.

```
Turn 1: Send [Stable (cached) + Context (cached) + Volatile]
         ↓ Upstream caches the stable+context prefix
Turn 2: Send [Cached prefix ID + Volatile]  ← Cheaper!
```

By rebuilding only when necessary (context compression), Hercules keeps the cache warm and reduces per-turn cost.

### Stability Guarantees

**Stable Tier** is never changed mid-session:
- SOUL.md is read once at session start
- Skills index is built once
- Model and tool configuration are fixed
- No tool definitions change mid-turn

**Context Tier** is stable within a session:
- AGENTS.md is read at session start
- Context files don't change during the session

**Volatile Tier** changes on every turn:
- Memory snapshots update
- Timestamp refreshes
- User messages are new

This design ensures:
1. Prompt caching stays warm (stable tier is identical across turns)
2. Flexibility (context can change between sessions)
3. Freshness (memory and messages are always current)

---

## Token Budget Best Practices

### "Every Character Counts"

System prompt and tool schemas are **fixed overhead on every API call**. Even one extra KB means 250+ extra tokens per 100-turn session.

### Optimize in Order

1. **Skills index** (largest single block)
   - Review installed skills: `hercules skills list`
   - Disable unused categories: `disabled_toolsets` in config.yaml
   - Typical savings: 5-20 KB

2. **Tool schemas** (second largest block)
   - Disable unused toolsets: `disabled_toolsets` in config.yaml
   - Typical savings: 10-30 KB

3. **Memory** (grows over time)
   - Archive old entries: `memory prune`
   - Keep active memories under 10 KB
   - Typical savings: 2-10 KB

4. **Context files** (AGENTS.md, .cursorrules)
   - Keep project guidance under 2 KB
   - Dynamic cap scales to your model's context window
   - No savings available (they're essential)

### Example Optimization

**Before:**
- System prompt: 35 KB
- Tools schemas: 75 KB
- Total fixed: 110 KB per turn

**After** (disable unused skills and toolsets):
- System prompt: 18 KB
- Tool schemas: 42 KB
- Total fixed: 60 KB per turn

**Savings:** 50 KB per turn = 50 KB × 100 turns = 5 MB per 100-turn session ≈ ~$0.15-0.50 depending on model.

---

## Prompt Injection & Safety

**Hercules does not scan context files for prompt injection.** All files on disk are assumed to be intentional:

- SOUL.md, AGENTS.md, .cursorrules are author-controlled
- They are not fetched from untrusted sources
- You wrote them; you own them

**Threat scanning is applied only to untrusted sources:**
- Web content (fetched with `web_search`, `web_fetch`)
- Browser screenshots and page contents
- User-uploaded files
- Tool results (wrapped in safety markers)

See [`content_trust.py`](../../../agent/content_trust.py) and [`approval.py`](../../../tools/approval.py) for safety details.

---

## See Also

- [`SOUL.md` Template Guide](./soul-md-template.md)
- [AGENTS.md](../../../AGENTS.md) — Development philosophy and contribution rubric
- [CLAUDE.md](../../../CLAUDE.md) — Operational guidance for the Hercules codebase
- [`hercules prompt-size --json`](../commands/tools.md#prompt-size) — JSON output for scripting
