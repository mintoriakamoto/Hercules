# Codebase Verification & Integrity Skill

**Purpose:** Comprehensive verification framework for 500k-line Python codebase. Validates architectural coherence, dependency integrity, performance boundaries, and cross-cutting concerns.

**Scope:** Backend agent runtime, tool dispatch, plugin ecosystem, consensus mechanisms, gateway daemon, CLI interfaces.

---

## Layer 1: Architectural Consistency Verification

### 1.1 Module Dependency Integrity

**What it does:** Validates that import hierarchies respect architectural boundaries.

**Why it matters:** 
- `hercules_cli/` has 408 lazy imports to avoid circular dependencies
- Hoisting a single import to module-level breaks the entire codebase
- Current system is fragile and implicit

**How to verify:**
```bash
# Find all lazy imports in hercules_cli
grep -r "def.*import" hercules_cli/ | grep -v "__pycache__"

# Verify they're function-local, never module-level
rg "^from|^import" hercules_cli/ --type py | grep -v "^hercules_cli/.*:    "
```

**Automated check needed:**
- Pre-commit hook that detects module-level imports in hercules_cli/
- Whitelist mechanism for intentional root-level imports
- CI failure on first violation with clear error message

### 1.2 Package Boundary Enforcement

**Boundaries (per CLAUDE.md):**
```
Entry points (CLI, gateway, ACP, cron)
    ↓ one-way dependency
Core agent runtime (run_agent.py, agent/)
    ↓ one-way dependency
Tools & toolsets (tools/, agent/transports)
    ↓ one-way dependency
Plugins & extensibility (plugins/, skills/)
```

**Violations to detect:**
- `agent/` importing from `gateway/`
- `tools/` importing from `hercules_cli/config` at module level
- `gateway/run.py` (21k lines) reaching into agent internals
- Circular imports through plugin registration

**Implementation:**
```python
# scripts/verify_architecture.py (to be written)
# 1. Build dependency graph from AST analysis
# 2. Validate against allowed edges
# 3. Report violations with file:line and suggestion
# 4. Measure blast radius of each violation
```

### 1.3 Plugin & Skill Isolation Audits

**Current state:** Plugins execute arbitrary `exec_module()` code with only config name gating.

**Gaps:**
- No capability-based sandboxing (skills have this, plugins don't)
- No audit trail of what each plugin imports/modifies
- `register_tool(override=True)` can shadow built-ins unconditionally for "bundled" tag

**Verification needed:**
```
For each plugin in ~/.hercules/plugins/:
  ✓ Audit what's imported (stdlib, third-party, internal)
  ✓ Audit what globals are modified
  ✓ Check for anti-patterns (hardcoded credentials, network access, FS writes)
  ✓ Verify it only registers tools, doesn't patch built-ins
  ✓ Measure execution time and memory impact
```

**Deliverable:** Pre-plugin-load audit script that fails loudly if:
- Plugin imports `subprocess`, `os.system`, `eval`, `exec` without justification
- Plugin modifies `sys.path`, `sys.modules`, or global builtins
- Plugin makes outbound network calls during init

---

## Layer 2: Dependency & Supply Chain Integrity

### 2.1 Exact Pinning with Bounds Validation

**Current state:** Exact pins with upper bounds enforced in CI.

**Gaps:**
- No transitive dependency audit (A pins B@1.2.3, but B pulls C@latest)
- No SLA tracking (when B@1.2.4 is released, how old is our pin?)
- No automated upgrade suggestions with changelog review

**Implementation needed:**

```python
# scripts/audit_transitive_deps.py
# 1. Generate full tree of transitive dependencies
# 2. Flag any transitive without explicit upper bound
# 3. Check for known vulnerabilities (OSV already does this)
# 4. Generate "upgrade available" report with SLA
# 5. Suggest which pins to bump + risk assessment
```

**Deliverable:** Monthly report showing:
- Pins older than 90 days (recommend review)
- Security updates available
- Breaking changes in new versions (detected from changelog parsing)

### 2.2 Optional Dependencies Consistency

**Current state:** `tools/lazy_deps.py` mirrors `pyproject.toml` extras. Test uses `--extra all` in CI.

**Gap:** Lazy-loaded modules are never verified to exist until runtime.

**Check needed:**
```bash
# Verify every function decorated @requires_extra exists only behind try/except
rg "@requires_extra|@optional_feature" --type py | while read line; do
  module=$(echo "$line" | cut -d: -f1)
  check_wrapped_in_try_except "$module"
done
```

**Deliverable:** Pre-release audit that:
- Lists all features hidden behind `--extra` flags
- Verifies each has fallback behavior or explicit FeatureUnavailable error
- Tests that missing optionals fail gracefully (not with ImportError)

---

## Layer 3: Performance & Scaling Boundaries

### 3.1 Tool Registry Scan Performance

**Current bottleneck:** ~0.4s AST scan of 114 tool files on every startup.

**Solution in place:** `tools/_builtin_module_cache.json` (fingerprint-based).

**Verification gaps:**
- Cache invalidation logic not tested
- No SLA on "startup time if cache hits" (should be <50ms)
- No measurement of cache hit rate in production

**Monitoring needed:**
```python
# agent/startup_metrics.py (to be written)
# 1. Measure time from start to "ready to accept commands"
# 2. Break it down: imports, tool registry, skills load, system prompt
# 3. Compare cached vs. uncached startup
# 4. Alert if any component regresses >50%
```

### 3.2 Skill Index Delta Delivery Latency

**New capability:** `agent/skills_index_delta.py` delivers skill changes mid-conversation.

**What to verify:**
- Note generation time (should be <10ms)
- Note size (should be <2KB for typical changes)
- Prefix cache stays warm (note is behind cached boundary)
- Model receives note on every turn it's staged (no silent drops)

**Test case:**
```python
def test_skills_index_delta_preserves_cache():
    # 1. Build prompt with skills index
    # 2. Stage a new skill via delta
    # 3. Verify note appears in user message sidecar
    # 4. Measure that prefix cache was reused (provider stats)
```

### 3.3 Consensus Mechanism Scaling

**Current state:** Standing consensus with rank, decay, reserved slice.

**No measurement for:**
- How many concurrent claims can the verifier handle?
- Proof replay latency at scale
- Storage growth of claim history
- Majority rule convergence time with Byzantine quorum

**Deliverable:** Load test suite
```python
# tests/test_consensus_scaling.py
def test_proof_replay_at_scale():
    # Generate 1000 claims, replay them
    # Measure time to consensus

def test_concurrent_claim_submission():
    # Submit 100 claims concurrently
    # Verify no race conditions, all verdicts consistent
```

---

## Layer 4: Security & Threat Surface Audits

### 4.1 Approval System Verification

**Inverted design:** Everything approved by default. No command-blocking guards.

**Gaps in verification:**
- No proof that every approval path returns `approved=True` before reaching callbacks
- No guarantee that dangerous-pattern detection returns False
- Session identity (`session_key` contextvar) could be spoofed if not set

**Automated check:**
```python
# scripts/verify_approval_inversion.py
# 1. Find all paths through _run_approval_gate
# 2. Verify each returns {"approved": True} before callback is ever called
# 3. Verify no approval code path blocks
# 4. Verify session_key is always set from gateway/CLI
# 5. Measure time to approval decision (should be <1ms)
```

### 4.2 Plugin Code Execution Audit

**Risk:** `exec_module()` with no integrity check.

**Mitigation:** Signed manifest per plugin (not yet implemented).

**Needed deliverable:**
```
For each plugin version:
  - Hash of __init__.py (SHA-256)
  - List of capabilities it uses (network, FS, subprocess)
  - Audit trail of what it registered
  - Last tested with which Hercules version
```

### 4.3 Skill Content Integrity

**Current:** SHA-256 hashing with 64-bit truncation legacy support.

**Verification gaps:**
- No check that installed skills match lockfile hashes
- No warning if skill is newer than declared
- No mechanism to revoke compromised skills

**Deliverable:** Pre-runtime skill audit
```python
def verify_skills_integrity():
    """
    1. Load skill lockfile (content hashes)
    2. Scan installed skills directory
    3. Verify each skill hash matches
    4. Report: which skills updated since lock
    5. Warn if any untracked skills found
    """
```

---

## Layer 5: Cross-Cutting Concern Validators

### 5.1 Logging Consistency

**Problem:** Logs at different levels (debug, info, warning, error) with no structure.

**Needed:**
```python
# scripts/audit_logging.py
# 1. Find all logger.xxx() calls
# 2. Verify error logs have exc_info=True when in except blocks
# 3. Verify no secrets in log output (credit cards, tokens, passwords)
# 4. Check log messages are actionable (not too generic)
# 5. Flag dead-code logging (logger.info in paths never executed)
```

### 5.2 Resource Cleanup Verification

**Risk areas:**
- Open files not closed
- Network connections left dangling
- Database transactions not committed/rolled back
- Temporary processes not terminated

**Audit needed:**
```python
# tests/test_resource_cleanup.py
# 1. Trace all context managers in agent execution
# 2. Verify __exit__ always called (even on exception)
# 3. Check subprocess.Popen has explicit cleanup
# 4. Verify temp files are cleaned up
```

### 5.3 Exception Handling Audit

**Gaps:**
- `except Exception:` blanket catches (good for robustness, bad for debugging)
- `pass` in except blocks (silently drops errors)
- Exceptions not re-raised when they should be

**Verification:**
```bash
# Find all except blocks with pass
rg "except.*:\s*pass" --type py

# Find all broad exception catches
rg "except Exception:" --type py | wc -l

# Check if exception is logged or re-raised
rg "except.*:\s*(?!.*(?:log|raise|return))" --type py
```

---

## Layer 6: Testing & Coverage Integrity

### 6.1 Test Isolation Verification

**Current issue:** Cross-test pollution in 225+ approval tests when run together.

**Solution:** `scripts/run_tests.sh` runs each file in subprocess.

**Gaps:**
- No detection of which tests pollute which other tests
- No measurement of pollution severity
- No enforcement that tests clean up after themselves

**Implementation:**
```python
# scripts/detect_test_pollution.py
# 1. Run tests in pairs: A alone, B alone, A+B together
# 2. If results differ, record A→B pollution
# 3. Build pollution graph
# 4. Report most-problematic tests to isolate
```

### 6.2 Coverage Depth Metrics

**Current:** Test existence + pytest passing. No depth measurement.

**Needed metrics:**
```
Per test:
  ✓ Does it test happy path?
  ✓ Does it test all error branches?
  ✓ Does it test boundary conditions?
  ✓ Does it mock external dependencies?
  
Per module:
  ✓ % of lines executed by tests
  ✓ % of branches covered
  ✓ % of exception paths tested
  ✓ Average assertions per test (too few = shallow)
```

**Deliverable:** Coverage audit report
```bash
pytest --cov=agent --cov-report=term --cov-fail-under=85
# Should fail if coverage drops below 85%
```

### 6.3 Property-Based Testing

**Currently missing:** No hypothesis/quickcheck tests.

**Candidates for property-based testing:**
- `detect_dangerous_command()` — Given any command string, returns consistent result
- `ContentApproval.is_still_valid_for()` — Hash comparison is symmetric
- `standing.py` rank/decay — Always converges to consensus
- `tool_call_batches.expand_local_tool_batches()` — Roundtrip invariant

**Deliverable:** Property test suite (e.g., with hypothesis)
```python
@given(command=st.text())
def test_dangerous_detection_is_deterministic(command):
    result1 = detect_dangerous_command(command)
    result2 = detect_dangerous_command(command)
    assert result1 == result2
```

---

## Layer 7: Documentation & Knowledge Integrity

### 7.1 CLAUDE.md Freshness

**Current:** Manually maintained architecture doc.

**Gaps:**
- No automated verification that it's accurate
- No enforced update when code changes
- Comments in code can drift from CLAUDE.md

**Verification:**
```python
# scripts/verify_claude_md.py
# 1. Parse CLAUDE.md architecture diagram
# 2. Scan actual imports to build real graph
# 3. Compare against declared architecture
# 4. Flag any modules in code not listed in doc
# 5. Flag any imports in doc not present in code
```

### 7.2 Skill Documentation Completeness

**Currently:** SKILL.md files loaded, but no quality audit.

**Needed:**
```
Per skill:
  ✓ Has description section
  ✓ Has use-case examples
  ✓ Lists all inputs/outputs
  ✓ Includes error cases
  ✓ No broken examples (verify they run)
  ✓ Mentions when it was last updated
```

### 7.3 API Stability Contract

**Missing:** No formal versioning of agent/tool APIs.

**Needed:**
```
Per public function/class:
  ✓ Stability level (stable, beta, experimental)
  ✓ Deprecation timeline (when old API removed)
  ✓ Migration guide (how to upgrade from old to new)
  ✓ Changelog entry
```

---

## Implementation Priority

### P0 (Blocking)
1. **Architectural consistency verifier** — Prevent future import-cycle disasters
2. **Plugin capability audit** — Security baseline before plugin loads
3. **Skill integrity audit** — Verify skill lockfile matches disk

### P1 (High Value)
4. **Approval system verification** — Prove inverted design is actually inverted
5. **Test isolation detector** — Prevent cross-test pollution regression
6. **Coverage depth metrics** — Know if tests are actually testing

### P2 (Nice to Have)
7. **Performance boundary validator** — Alert on startup time regression
8. **Dependency SLA tracker** — Know which pins are stale
9. **Property-based tests** — Verify invariants hold at scale

### P3 (Long Term)
10. **Documentation freshness checker** — Keep CLAUDE.md accurate
11. **Resource cleanup verifier** — Prevent leaks
12. **Exception handling audit** — Improve debuggability

---

## Skill Invocation Pattern

```bash
# As a hook on every commit
python scripts/verify_architecture.py
python scripts/verify_approval_inversion.py

# As a pre-release check
python scripts/audit_transitive_deps.py
python scripts/detect_test_pollution.py
pytest --cov=agent --cov-fail-under=85

# As a plugin installation hook
python scripts/audit_plugin_capabilities.py ~/.hercules/plugins/new_plugin
python scripts/verify_skills_integrity.py
```

---

## Success Criteria

A mature codebase verification system looks like:

✅ **No silent failures** — Every code path has an explicit check  
✅ **Measurable boundaries** — Performance, security, and architectural limits quantified  
✅ **Automated enforcement** — CI fails before code reaches main  
✅ **Observable degradation** — Trends over time (startup time, test count, coverage)  
✅ **Operator visibility** — Team can answer "is the codebase getting better or worse?"  

---

**Attribution:** Design pattern from verification systems used in financial trading engines and kernel development. The multi-layer approach (architectural → dependency → performance → security → testing → documentation) prevents issues from compounding across concerns.
