# Desktop Engineering Guide

**For**: Engineers building the Hercules Desktop app (Electron + React).

This is a **judgment guide**, not an inventory — it teaches invariants and reasoning so changes fit
the app as files move. Read it alongside the repository `AGENTS.md` (root principles still apply
everywhere) and [`DESIGN.md`](./DESIGN.md) (visual and interaction contract).

**Invariant priority**: When a rule here and the code disagree, trust the code and fix whichever is
wrong — but **never break an invariant** to make a change easier.

---

## Quick Navigation

1. **[What this app is](#what-this-app-is)** — Architecture and separation of concerns
2. **[Decide state by authority](#decide-state-by-authority)** — State ownership and scope
3. **[Identity is not incidental](#identity-is-not-incidental)** — Session and entity identity
4. **[Server truth is cached, not owned](#server-truth-is-cached-not-owned)** — Cache semantics
5. **[Switching context](#switching-context-is-a-re-home-not-a-reboot)** — Profile and mode changes
6. **[Cross-platform resolution](#cross-everything-as-an-observable-ladder)** — Compatibility and fallbacks
7. **[UX principles](#respect-the-person-using-it)** — User-focused design rules
8. **[Performance](#make-it-feel-instant)** — Responsiveness and efficiency

---

## What this app is

Desktop is a **separate, native chat surface** for Hercules. Understand what it is **not**:
- **Not** the browser dashboard (`hercules dashboard` / web UI)
- **Not** an embedded TUI (the main CLI remains its own surface)
- **Not** a thin wrapper — it has distinct state, routing, and curation logic

### Three separate authorities

Each layer is authoritative for one thing:

1. **Electron** owns the machine layer
   - Process lifecycle, install/update, OS integration
   - Native filesystem, git access, window management
   - Single-threaded IPC bridge with typewritten schemas (narrow, deliberate)

2. **React renderer** owns the user experience layer
   - Navigation, presentation, ephemeral UI state
   - Local composition and interaction detail
   - No business logic, no session/tool knowledge

3. **Python agent backend** owns all work
   - Sessions, tool execution, model calls, streaming
   - Routing, memory, skill management
   - Authorization and credential handling

### Keep the seams clean

- The renderer **never** reaches into Node or Electron directly; capability arrives through
  a deliberate IPC schema, never an escape hatch.
- Agent behavior **lives behind the gateway**, never reimplemented in React for Desktop.
- When a change blurs a seam, that is the smell — **fix the seam, don't widen it**.
- If you find yourself adding special Desktop logic to core (run_agent.py, cli.py, gateway),
  stop and reconsider the architecture.

## Decide state by authority

The first question for any piece of state is **"Who is allowed to be right about it?"**, not
where it's convenient to store it. Put state with its authority:

| Authority | Owns | Examples | Treat as |
|-----------|------|----------|----------|
| **Backend** | Anything shared with other Hercules surfaces | Sessions, memory, skills, tools, config | Cache (validate before use) |
| **Electron** | Machine & runtime facts | Window state, clipboard, file paths, installed version | Source of truth |
| **Renderer** | Only this window's presentation | Expanded/collapsed UI sections, scroll position, theme override | Local-only state |

### Layering state within the renderer

From authority comes hierarchy — reach for the narrowest scope that keeps state correct:

1. **Component state** — short-lived interaction detail (hover, focus, drag)
2. **Feature store** — request-shaped data that the feature owns (the model picker's visible list)
3. **Shared store** — state read by many distant surfaces (active session, connection mode)
4. **URL/routing** — state that should serialize in browser history (open chat, focused item)
5. **LocalStorage** — ephemeral per-viewer convenience (last theme, window size) — **never** shared user data

**Rule**: A new **global store** is a claim that many distant features need it. Earn that claim.

### Scope in persistence keys

Persisted state must declare its scope in its own key. A misnamed scope is how one profile's
setting bleeds into another, or a user's preference overwrites the team's:

- **Global** — `theme` (all users, all profiles)
- **Profile-scoped** — `profile:${profileName}:lastSession` (one profile's state)
- **Connection-scoped** — `connection:${connectionId}:apiVersion` (applies to one backend)
- **User-scoped** — `user:${userId}:openSessions` (one person's pinned items, even across profiles)
- **Window-scoped** — `window:${windowId}:sidebarWidth` (this window only)

## Identity is not incidental

Sessions have more than one identity, and conflating them is a recurring source
of "session not found" and vanishing history. Reason about which identity a
surface needs: durable navigation and anything the user pins or persists key off
the stable/durable identity; live streaming keys off the runtime identity; state
that must outlive compression keys off the lineage root. Keep the mapping between
them explicit and translate at the boundary rather than passing the wrong id
inward.

## Server truth is cached, not owned

The renderer paints from a cache of backend truth. It must reconcile new info with what it knows,
never blindly replace. This is load-bearing: async bugs lurk here.

### Reconciliation rules

| Rule | Why | Do | Don't |
|------|-----|----|----|
| **Merge, not clobber** | Refresh is new data *over* what you know | Layer session changes onto live rows | Replace entire list, losing pinned/live state |
| **Optimistic then honest** | User sees intent immediately; async failure rolls back visibly | Paint directly from snapshot; refresh corrects later | Wait for server; paint only on success |
| **Guard async order** | Requests complete out of order; stale response shouldn't win | Use generation counters, request tokens | Assume responses = request order |
| **Foreground only publishes** | Prevent background sync from hijacking the view | Only active surface writes to shared stores | Background work updates shared state |
| **Batch cosmetic, flush signal** | High-frequency scroll noise hides real changes | Coalesce 100 scroll pixels into one update | Debounce terminal transitions (turn end, needing input) |
| **Preserve reference identity** | React does shallow comparison; new array = re-render | Keep same array object when data doesn't change | Create fresh array even for no-op refresh |

### Pattern: Optimistic updates

```typescript
// 1. Update local cache immediately (optimistic)
sessionStore.updateSession(sessionId, {isArchived: true});
render(); // User sees change now

// 2. Call backend
api.archiveSession(sessionId)
  .then(result => {
    // 3. Merge server's authoritative version over what we know
    sessionStore.updateSession(sessionId, result);
  })
  .catch(err => {
    // 4. Rollback visibly if write fails
    sessionStore.updateSession(sessionId, {isArchived: false});
    showError("Could not archive session");
  });
```

## Switching context is a re-home, not a reboot

Changing profile, connection, or mode is a **workspace switch**, not a cold start. The shell,
tools, and what the user was doing stay put. Only gateway-bound state resets, and previous
context must not leak into the next one. Reserve the full-screen boot/connecting experience only
for a genuinely unusable backend.

### Three switch shapes (conflating them is the classic bug)

| Switch Type | Triggered by | Stores | API/Socket | State | Result |
|-------------|--------------|--------|------------|-------|--------|
| **Soft re-home** | Connection/mode change (local ↔ remote ↔ cloud) | Explicitly wipe gateway stores | Reconnect to new socket | Shell/window preserved | UI reprints from fresh queries |
| **Hard re-home** | Runtime profile change (`HERCULES_HOME` switch) | Full app reload | New process entirely | Complete reset | Browser reload behavior |
| **Live profile swap** | User switches profile in dropdown | Merge lists, keep background threads | Keep old socket open | Background streams continue | New profile layers in, old listens for updates |

**Critical**: Query invalidation alone cannot evict live session stores. Soft switches must
**explicitly wipe** gateway-bound stores before reconnecting.

**After any swap**, validate the invariant: `activeSocket + activeProfile + connectionMode` must agree,
or REST calls and filesystem access route to the wrong backend (users see wrong sessions, tools fail).

### Consequences of getting it wrong

- **Soft as hard** → App flickers, user loses context, background work stops
- **Hard as soft** → Stale rows from old profile appear, user edits wrong thing
- **Profile swap broken** → Background still streaming old profile, new selection ignored

## Cross everything as an observable ladder

Desktop lives at the seams: versions, profiles, local vs remote vs cloud, partially installed
runtimes, stale caches, older backends. Every integration point uses the same durable pattern:
an **ordered ladder of candidates** with validation at each rung.

### The pattern (6 rules)

1. **Precedence is explicit** — written once as data or a pure function (not scattered across call sites)
2. **Validate at the boundary** — existence ≠ correctness; always probe before trusting
3. **Failed read falls through** — try next rung. Failed write surfaces or rolls back explicitly (never silent retarget)
4. **Distinguish missing from transient** — missing capability → compatibility path / disabled state; transient failure → retry
5. **Bound retries, surface recovery** — never infinite spinner or hot loop; always give user a way forward
6. **One resolver owns policy** — every caller gets the same answer; scatter = bugs

### Applications

This pattern governs: backend discovery, version fallbacks, auth resolution, workspace path
selection, capability detection, preview generation, and config inheritance. **Learn the shape,
not the current rungs** — the rungs change, the pattern stays.

### Auth corollaries (easy to get wrong)

**One-time credentials are never reused.**
- OAuth gateway mint: fresh WebSocket ticket on every dial
- Mint failure → reauthenticate (don't fall back to cached URL)
- Exception: long-lived tokens/local auth may reuse cached URL as lower rung

**Test the path you'll use.**
- HTTP status probe passing ≠ WebSocket/auth working
- Probe must exercise the full leg (HTTP + auth upgrade, not just status)
- False-positive connection check breaks the entire flow

## Compatibility without carrying the past forever

Desktop and its runtime update on separate clocks — a change can land against an older backend.
Keep those users working:

1. **Preserve the current feature** — don't degrade to an older interaction
2. **Keep fallback narrow** — tied to an identified older version, not a broad guess
3. **Cover it with a test** — fallback behavior must be verified (dead fallbacks silently rot)

**Anti-pattern**: A fallback that degrades the feature it protects is worse than the crash it
replaced. Example: detecting old version and silently skipping a feature leaves users thinking
it's not installed, not that it's incompatible.

---

## Keep the waist narrow, grow at the edges

The root `AGENTS.md` contribution rubric governs here too: extend code before inventing new
infrastructure. For Desktop:

- **Extend what exists** — compose existing screens before building new ones
- **Add a feature locally** — surface-specific state stays at the surface
- **Lean on existing seams** — use the command registry, existing stores, query patterns
- **Then a framework** — only after two real consumers prove the contract

**Don't build**: universal extension systems, plugin manifests, or adapter layers for one consumer.
Shell registries are composition seams, not a public ABI. "Plugin" means different things across
Hercules — don't assume one surface's model works elsewhere.

---

## Respect the person using it

Design and engineering meet at intent. The user's attention and context are **sacred**:

| Principle | Do | Don't |
|-----------|-------|----------|
| **User controls navigation** | Highlight new info, offer navigation | Navigate/focus-steal from background events |
| **Loading is distinct UX** | Empty, loading, reconnecting, degraded, exhausted each get honest copy + exit | Generic spinner that hides the real state |
| **Keyboard is local** | Focused surface owns its keys; one cancel does one thing | Global shortcuts that collide with input |
| **Expensive surfaces stay alive when hidden** | Keep terminal running; visibility ≠ lifecycle | Tear down and recreate terminal on hide/show |

---

## Make it feel instant

Performance is a feature **the user feels**. Critical surfaces: drag, resize, scroll, typing,
streaming, terminals. Principles are timeless even as code changes:

- **Hot-path state** → local or narrowly derived (no distant subscriptions)
- **Heavy trees** → don't subscribe to per-frame updates (use memoization, coalesce)
- **Pointer work** → batch/throttle (drag events fire per pixel, not per intent)
- **Layout thrash** → avoid reading layout after writing style (batch reads, then writes)
- **Mid-gesture mounts** → don't render expensive components during drag/scroll
- **Prove against real content** → empty demo is not proof; test with long transcripts
- **No motion masking** → if motion hides latency, remove the motion and show the truth

---

## Testing as proof of behavior

Test behavior that breaks users, not data snapshots. Favor invariants over frozen values.
Exercise the real path for anything at a seam:

- **Resolver precedence + failure rungs** — does fallback actually work?
- **Identity & scope boundaries** — does state leak between profiles/windows/connections?
- **Optimistic rollback + async ordering** — does failed write rollback visibly?
- **Local/remote adapter** — both code paths with routing intact
- **Match suite reality** — use the same test runner, env setup, and isolation the CI uses

---

## Pre-handoff checklist

Before you consider the change done, verify:

- [ ] **State authority** — every piece lives with its authority, at narrowest scope?
- [ ] **Background isolation** — background events never steal foreground or focus?
- [ ] **Resolvers** — each policy has one home, a validated ladder, bounded retry, real recovery?
- [ ] **Routing agreement** — do local, remote, and profile routing still align?
- [ ] **Failure UX** — does async failure leave a usable surface + way forward?
- [ ] **Performance** — hot interactions cheap under realistic load (real content, not demo)?
- [ ] **Design contract** — does change pass [`DESIGN.md`](./DESIGN.md) checklist and update all locales?

If any answer is "not sure," **go verify that part**. Hunch-driven shipping is how subtle bugs land.
