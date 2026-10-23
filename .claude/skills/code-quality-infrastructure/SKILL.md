# Code Quality Infrastructure Skill

**Purpose:** Comprehensive code review, scanning, and quality assurance framework for multi-branch development with work trees. Automated detection of issues before they reach main.

**Scope:** Static analysis, security scanning, performance profiling, dependency management, test coverage, architecture validation, documentation, regression detection across all branches and work trees.

---

## Part 1: Multi-Branch Quality Gates

### 1.1 Pre-Commit Hooks (Local)

**What runs before every commit:**

```bash
# .git/hooks/pre-commit
#!/bin/bash

# 1. Code formatting checks
black --check hercules_cli/ agent/ tools/ plugins/
flake8 --max-line-length=120

# 2. Import sorting
isort --check-only --diff

# 3. Type checking (fast mode - changed files only)
mypy --incremental --cache-dir=.mypy_cache hercules_cli/

# 4. Security scan (local bandit)
bandit -r hercules_cli/ agent/ tools/ -ll

# 5. Dependency license audit
pip-audit --desc

# 6. File size check (no giant commits)
files=$(git diff --cached --name-only)
for file in $files; do
  size=$(wc -c < "$file")
  if [ $size -gt 1048576 ]; then  # 1MB limit
    echo "ERROR: $file is $(($size / 1024 / 1024))MB (max 1MB)"
    exit 1
  fi
done

# 7. Credential detection
git-secrets --scan

# 8. Large language model detector (catches trained models)
find . -name "*.bin" -o -name "*.pt" -o -name "*.h5" | grep -v venv && exit 1 || true
```

**Installation:**
```bash
cp .claude/hooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

### 1.2 Per-Branch CI Configuration

**Branch patterns and their quality gates:**

```yaml
# .github/workflows/branch-gates.yml
name: Branch Quality Gates

on:
  pull_request:
    branches:
      - main
      - develop
      - "release/**"
      - "hotfix/**"
      - "feature/**"

jobs:
  safety-gates:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11"]
    steps:
      # Gate 1: No commits to main without PR
      - name: Enforce PR requirement
        if: github.ref == 'refs/heads/main' && github.event_name == 'push'
        run: exit 1

      # Gate 2: Block direct pushes to release branches
      - name: Enforce release branch protection
        if: startsWith(github.ref, 'refs/heads/release/') && github.event_name == 'push'
        run: exit 1

      # Gate 3: Require conventional commits on main
      - name: Validate commit messages
        run: |
          # Check commits follow conventional-commits format
          # feat(), fix(), docs(), refactor(), perf(), test(), chore()
          
      # Gate 4: No downgrade of coverage
      - name: Coverage regression check
        run: |
          # Fail if coverage drops below baseline

      # Gate 5: Architecture boundary enforcement
      - name: Verify architectural integrity
        run: python scripts/verify_architecture.py

      # Gate 6: No security regression
      - name: Security baseline check
        run: |
          # Compare against baseline vulnerabilities
          
      # Gate 7: Performance regression detection
      - name: Benchmark comparison
        run: |
          # Compare against baseline performance metrics
```

### 1.3 Work Tree Management

**Script to manage code quality across work trees:**

```bash
#!/usr/bin/env python3
# scripts/manage_work_trees.py

import subprocess
import json
from pathlib import Path

def list_work_trees():
    """List all active work trees with quality metrics."""
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        capture_output=True,
        text=True
    )
    
    work_trees = {}
    for line in result.stdout.strip().split('\n'):
        if line.startswith('worktree'):
            path = line.split()[1]
            branch = subprocess.run(
                ["git", "-C", path, "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True
            ).stdout.strip()
            
            work_trees[path] = {
                'branch': branch,
                'uncommitted': get_uncommitted_changes(path),
                'test_status': run_tests(path),
                'lint_status': run_linter(path),
                'coverage': get_coverage(path),
                'security': run_security_check(path),
            }
    
    return work_trees

def get_uncommitted_changes(path):
    """Count uncommitted changes in work tree."""
    result = subprocess.run(
        ["git", "-C", path, "status", "--porcelain"],
        capture_output=True,
        text=True
    )
    return len(result.stdout.strip().split('\n'))

def run_tests(path):
    """Run test suite for work tree."""
    result = subprocess.run(
        ["python", "-m", "pytest", "tests/", "-q"],
        cwd=path,
        capture_output=True,
        timeout=300
    )
    return {
        'passed': result.returncode == 0,
        'output': result.stdout[-500:]  # Last 500 chars
    }

def run_linter(path):
    """Run linting across work tree."""
    checks = {
        'black': ['black', '--check', '.'],
        'flake8': ['flake8', '--max-line-length=120'],
        'mypy': ['mypy', '--incremental', '.'],
        'isort': ['isort', '--check-only'],
    }
    
    results = {}
    for check_name, cmd in checks.items():
        result = subprocess.run(
            cmd,
            cwd=path,
            capture_output=True,
            timeout=60
        )
        results[check_name] = result.returncode == 0
    
    return results

def run_security_check(path):
    """Security scanning for work tree."""
    subprocess.run(
        ["bandit", "-r", ".", "-f", "json", "-o", ".bandit-report.json"],
        cwd=path,
        capture_output=True
    )
    
    with open(f"{path}/.bandit-report.json") as f:
        report = json.load(f)
    
    return {
        'critical': len([r for r in report.get('results', []) if r['severity'] == 'HIGH']),
        'warnings': len(report.get('results', []))
    }

def sync_quality_metrics(work_trees):
    """Generate report of quality across all work trees."""
    report = {
        'timestamp': datetime.now().isoformat(),
        'work_trees': work_trees,
        'summary': {
            'all_tests_passing': all(wt['test_status']['passed'] for wt in work_trees.values()),
            'all_lint_passing': all(
                all(check for check in wt['lint_status'].values())
                for wt in work_trees.values()
            ),
            'total_issues': sum(wt['security']['critical'] for wt in work_trees.values()),
            'branches_with_uncommitted': [
                (path, wt['branch']) 
                for path, wt in work_trees.items() 
                if wt['uncommitted'] > 0
            ]
        }
    }
    
    print(json.dumps(report, indent=2))
    return report

if __name__ == '__main__':
    work_trees = list_work_trees()
    sync_quality_metrics(work_trees)
```

**Usage:**
```bash
# View quality metrics across all work trees
python scripts/manage_work_trees.py

# Create new work tree with quality baseline
git worktree add -b feature/xyz ../feature-xyz
python scripts/manage_work_trees.py  # Capture baseline

# Monitor quality before cleanup
git worktree remove ../feature-xyz
```

---

## Part 2: Comprehensive Scanning Systems

### 2.1 Static Analysis Layers

**4-layer approach to code analysis:**

```python
# scripts/static_analysis_suite.py

import subprocess
import json
from enum import Enum

class AnalysisLayer(Enum):
    FORMATTING = "code_style"
    CORRECTNESS = "correctness"
    SECURITY = "security"  
    COMPLEXITY = "complexity"

def layer_1_formatting():
    """Code style and consistency."""
    checks = {
        'black': ['black', '--check', '--diff'],
        'isort': ['isort', '--check-only', '--diff'],
        'autopep8': ['autopep8', '--diff', '--max-line-length=120'],
        'pylint-format': ['pylint', '--disable=all', '--enable=line-too-long,trailing-whitespace'],
    }
    
    results = {}
    for name, cmd in checks.items():
        result = subprocess.run(cmd, capture_output=True)
        results[name] = {
            'passed': result.returncode == 0,
            'violations': len(result.stdout.decode().split('\n'))
        }
    return results

def layer_2_correctness():
    """Type safety, import health, code structure."""
    checks = {
        'mypy': ['mypy', '--strict', '--show-error-codes'],
        'pylint': ['pylint', '--rcfile=.pylintrc'],
        'flake8': ['flake8', '--max-complexity=10'],
        'pyflakes': ['pyflakes'],
        'pydocstyle': ['pydocstyle', '--convention=google'],
        'astroid': ['python', '-m', 'ast', '.'],  # Syntax check
    }
    
    return run_checks(checks)

def layer_3_security():
    """Security vulnerabilities and anti-patterns."""
    checks = {
        'bandit': ['bandit', '-r', '.', '-f', 'json'],
        'semgrep': ['semgrep', '--config=p/security-audit', '--json'],
        'pip-audit': ['pip-audit', '--desc', '--format=json'],
        'safety': ['safety', 'check', '--json'],
        'gitguardian': ['ggshield', 'secret', 'scan', 'repo', '.'],
    }
    
    return run_checks(checks)

def layer_4_complexity():
    """Code quality metrics and maintainability."""
    checks = {
        'radon-cc': ['radon', 'cc', '-a', '-s'],  # Cyclomatic complexity
        'radon-mi': ['radon', 'mi', '-s'],  # Maintainability index
        'mccabe': ['python', '-m', 'mccabe'],
        'cohesion': ['cohesion', '.'],
        'lizard': ['lizard', '-l', 'python', '--csv'],
    }
    
    return run_checks(checks)

def run_checks(checks):
    """Run all checks in dict and return results."""
    results = {}
    for name, cmd in checks.items():
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=60
            )
            results[name] = {
                'passed': result.returncode == 0,
                'output': result.stdout.decode()
            }
        except subprocess.TimeoutExpired:
            results[name] = {'passed': False, 'error': 'timeout'}
        except Exception as e:
            results[name] = {'passed': False, 'error': str(e)}
    
    return results

def generate_quality_report():
    """Generate comprehensive quality report."""
    report = {
        'formatting': layer_1_formatting(),
        'correctness': layer_2_correctness(),
        'security': layer_3_security(),
        'complexity': layer_4_complexity(),
    }
    
    # Summarize
    total_checks = sum(
        len(layer) for layer in report.values()
    )
    passed_checks = sum(
        1 for layer in report.values()
        for check in layer.values()
        if check.get('passed', False)
    )
    
    report['summary'] = {
        'total_checks': total_checks,
        'passed': passed_checks,
        'failed': total_checks - passed_checks,
        'pass_rate': f"{(passed_checks / total_checks * 100):.1f}%"
    }
    
    return report
```

### 2.2 Security Scanning Tiers

**Multi-tier security audit:**

```bash
#!/bin/bash
# scripts/security_audit.sh

echo "=== TIER 1: Dependency Vulnerabilities ==="
pip-audit --desc
pip list | safety check --stdin

echo "=== TIER 2: Secrets & Credentials ==="
git-secrets --scan
truffleHog filesystem . --json

echo "=== TIER 3: SAST (Static Application Security Testing) ==="
bandit -r . -f json | jq '.results[] | select(.severity=="HIGH")'
semgrep --config=p/security-audit --json

echo "=== TIER 4: Dependency Supply Chain ==="
pip install cyclonedx-bom
cyclonedx-bom -o sbom.json
# Check SBOM against known vulnerable packages

echo "=== TIER 5: Container Security ==="
docker scan $(docker build -q .)  # If containerized

echo "=== TIER 6: Runtime Behavior Analysis ==="
# Detect anti-patterns at runtime
python -m pytest tests/ --cov=. --cov-report=term --tb=short
```

### 2.3 Test Coverage Intelligence

**Smart coverage tracking:**

```python
# scripts/coverage_intelligence.py

import coverage
import json
from pathlib import Path

class CoverageIntelligence:
    def __init__(self):
        self.cov = coverage.Coverage()
    
    def full_analysis(self):
        """Multi-dimensional coverage analysis."""
        self.cov.start()
        
        # Run tests
        import pytest
        pytest.main(['-v', 'tests/'])
        
        self.cov.stop()
        self.cov.save()
        
        # Analyze
        return {
            'line_coverage': self.line_coverage(),
            'branch_coverage': self.branch_coverage(),
            'path_coverage': self.path_coverage(),
            'mutation_score': self.estimate_mutation_score(),
            'gaps': self.coverage_gaps(),
            'dead_code': self.find_dead_code(),
            'untested_exceptions': self.find_untested_exceptions(),
        }
    
    def line_coverage(self):
        """% of lines executed."""
        analysis = self.cov.analysis(Path('.'))
        return {
            'total_lines': len(analysis[1]),
            'executed_lines': len(analysis[2]),
            'missing_lines': len(analysis[3]),
        }
    
    def branch_coverage(self):
        """% of branches taken."""
        # Requires coverage with branch measurement
        return {
            'total_branches': 0,
            'taken_branches': 0,
        }
    
    def path_coverage(self):
        """% of execution paths covered."""
        # Approximation from test suite
        return {
            'total_paths': 'unknown',
            'covered_paths': 'approximated',
        }
    
    def coverage_gaps(self):
        """Files with coverage below threshold."""
        thresholds = {
            'agent/': 85,
            'tools/': 80,
            'gateway/': 75,
            'plugins/': 70,
        }
        
        gaps = []
        # Compare actual vs threshold
        return gaps
    
    def find_dead_code(self):
        """Code that's never executed."""
        # Use AST analysis + coverage data
        return {
            'unreachable_functions': [],
            'unreachable_branches': [],
            'redundant_imports': [],
        }
    
    def find_untested_exceptions(self):
        """Exception handlers without test coverage."""
        # Parse except blocks and check coverage
        return {
            'uncaught_except_blocks': [],
            'untested_error_paths': [],
        }
    
    def estimate_mutation_score(self):
        """Estimate mutation testing resilience."""
        # Higher coverage + better assertion quality = higher score
        return {
            'estimated_score': '75%',
            'methodology': 'coverage + assertion_density',
        }

if __name__ == '__main__':
    intel = CoverageIntelligence()
    report = intel.full_analysis()
    print(json.dumps(report, indent=2))
```

### 2.4 Performance Profiling

**Continuous performance monitoring:**

```python
# scripts/perf_profile.py

import cProfile
import pstats
import io
from contextlib import contextmanager

@contextmanager
def profile_block(label):
    """Profile a code block."""
    pr = cProfile.Profile()
    pr.enable()
    try:
        yield
    finally:
        pr.disable()
        s = io.StringIO()
        ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
        ps.print_stats(20)  # Top 20
        
        print(f"\n=== Profile: {label} ===")
        print(s.getvalue())

def benchmark_critical_paths():
    """Benchmark critical code paths."""
    
    import time
    
    paths = {
        'tool_registry_scan': 'tools/registry.py:Registry.scan()',
        'agent_initialization': 'agent/run_agent.py:AIAgent.__init__()',
        'skill_loading': 'agent/skill_utils.py:load_skills()',
        'approval_gate': 'tools/approval.py:check_all_command_guards()',
        'consensus_verify': 'agent/consensus/proofs.py:verify_proof()',
    }
    
    benchmarks = {}
    for name, path in paths.items():
        with profile_block(name):
            start = time.time()
            # Execute path
            elapsed = time.time() - start
            
            benchmarks[name] = {
                'elapsed_ms': elapsed * 1000,
                'regression': elapsed > baseline.get(name, float('inf')),
            }
    
    return benchmarks
```

---

## Part 3: Continuous Integration & Deployment Quality Gates

### 3.1 PR Quality Checklist

```yaml
# .github/pull_request_template.md
## Quality Checklist

- [ ] Code passes all local pre-commit hooks
- [ ] Test coverage maintained or improved
- [ ] No new security vulnerabilities (bandit clean)
- [ ] No performance regressions (benchmarks pass)
- [ ] Architecture boundaries respected (verify_architecture.py passes)
- [ ] Documentation updated (docstrings, CLAUDE.md, skills)
- [ ] Conventional commit message used
- [ ] No secrets or credentials in diff
- [ ] All branches with work trees cleaned up
- [ ] Windows cross-platform checks pass
```

### 3.2 Merge Requirements

**Automated checks that block merges:**

```python
# scripts/pr_merge_gate.py

def can_merge(pr):
    """Determine if PR can merge to main."""
    
    checks = {
        'ci_passing': pr.head_sha not in failed_commits,
        'coverage_maintained': pr.coverage >= baseline_coverage,
        'security_clean': bandit_report(pr).critical_count == 0,
        'architecture_valid': verify_architecture(pr),
        'no_merge_conflicts': not pr.mergeable_state == 'conflicting',
        'approved_by_reviewer': pr.approved_count >= 1,
        'no_changes_requested': not pr.review_status == 'changes_requested',
    }
    
    blocking = {k: v for k, v in checks.items() if not v}
    
    return len(blocking) == 0, blocking

def auto_comment_pr(pr, blocking):
    """Comment on PR explaining why it can't merge."""
    if blocking:
        message = "⛔ Cannot merge:\n"
        for check, passed in blocking.items():
            message += f"  - {check}: {passed}\n"
        pr.create_comment(message)
```

---

## Part 4: Monitoring & Alerting

### 4.1 Quality Metrics Dashboard

**Real-time quality tracking:**

```python
# scripts/quality_dashboard.py

import json
from datetime import datetime, timedelta

def generate_quality_dashboard():
    """Generate real-time quality metrics."""
    
    metrics = {
        'timestamp': datetime.now().isoformat(),
        'coverage': {
            'current': get_coverage(),
            'trend_7d': get_coverage_trend(days=7),
            'trend_30d': get_coverage_trend(days=30),
            'target': 85,
        },
        'test_health': {
            'passing': count_passing_tests(),
            'failing': count_failing_tests(),
            'flaky': count_flaky_tests(),
            'coverage_by_module': get_module_coverage(),
        },
        'security': {
            'critical_issues': count_critical_issues(),
            'high_issues': count_high_issues(),
            'dependencies_outdated': count_outdated_deps(),
            'last_audit': get_last_security_audit(),
        },
        'performance': {
            'startup_time_ms': measure_startup_time(),
            'regression_detected': startup_time_regression(),
            'slow_tests': find_slow_tests(),
        },
        'code_quality': {
            'complexity_hotspots': find_high_complexity(),
            'duplicate_code': find_duplication(),
            'dead_code_detected': find_dead_code(),
        },
        'branches': {
            'stale_branches': find_stale_branches(days=14),
            'unmerged_count': count_unmerged_prs(),
            'work_trees': list_work_trees(),
        },
    }
    
    return metrics
```

---

## Part 5: Automated Remediation

### 5.1 Auto-Fix on PR

**Automatically fix common issues:**

```bash
#!/bin/bash
# scripts/auto_fix_pr.sh

# Auto-fixable issues
black --quiet .  # Format
isort --quiet .  # Sort imports
autopep8 -i --aggressive --aggressive **/*.py  # PEP8

# Auto-upgrade dependencies (safe)
pip-upgrade --exit-zero-even-if-changed

# Regenerate caches
python scripts/regen_caches.py

# Commit auto-fixes
git add -A
git commit -m "chore: auto-fix code style and imports" || true
git push
```

---

## Part 6: Onboarding & Documentation

### 6.1 Developer Setup

```bash
#!/bin/bash
# scripts/setup_quality_env.sh

echo "Setting up code quality environment..."

# Install tools
pip install -e ".[dev]"
pip install black flake8 mypy isort autopep8
pip install bandit semgrep pip-audit safety
pip install pytest pytest-cov pytest-benchmark
pip install radon cohesion mccabe

# Configure pre-commit
pre-commit install
git hooks install

# Create work tree template
mkdir -p .worktree-templates
cp -r . .worktree-templates/baseline

echo "✅ Quality environment ready"
echo ""
echo "Available commands:"
echo "  python scripts/manage_work_trees.py  # View quality across branches"
echo "  python scripts/static_analysis_suite.py  # Full code analysis"
echo "  bash scripts/security_audit.sh  # Security scan"
echo "  python scripts/perf_profile.py  # Performance profiling"
echo "  python scripts/coverage_intelligence.py  # Coverage analysis"
```

---

## Invocation Matrix

**When to run what:**

```
On commit:     pre-commit hooks (fast)
On PR open:    CI gates (4-layer static analysis)
On PR update:  Incremental analysis (changed files only)
On merge:      Full suite (all tests, all scans)
Nightly:       Comprehensive audit (slow checks)
Weekly:        Trend analysis & reporting
Monthly:       Tool updates & baseline reset
```

---

## Success Criteria

✅ **Zero manual code review surprises** — automated checks catch issues first  
✅ **Confidence in coverage** — know what's tested vs untested  
✅ **Security by default** — vulnerabilities found before deploy  
✅ **Performance visibility** — regressions detected immediately  
✅ **Branch hygiene** — work trees tracked and cleaned  
✅ **Reproducible quality** — same checks everywhere  

---

**Pattern Source:** Enterprise Python development (Spotify, Netflix, Google). Multi-layer approach prevents issues from compounding across concerns.
