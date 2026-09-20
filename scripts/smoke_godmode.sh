#!/usr/bin/env bash
# Smoke: G0DM0D3 sidecar + every bundled Hercules model provider. No AGPL vendor.
# Safe to run from any cwd. Discovers plugins so new providers cannot drift off the list.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"
ROOT="${HERCULES_HOME:-$HOME/.hercules}"
SIDECAR="$ROOT/G0DM0D3"
fail=0

echo "== repo $REPO_ROOT"
echo "== in-tree model providers (discovered)"
count=0
while IFS= read -r p; do
  name="$(basename "$(dirname "$p")")"
  echo "OK $name"
  count=$((count + 1))
done < <(find plugins/model-providers -mindepth 2 -maxdepth 2 -name '__init__.py' | sort)
if [[ "$count" -lt 20 ]]; then echo "FAIL expected >=20 providers, got $count"; fail=1; fi
echo "provider_count=$count"

echo "== core files"
for p in hercules_cli/default_soul.py hercules_cli/runtime_provider.py hercules_cli/auth.py hercules_cli/model_switch.py agent/auxiliary_client.py tools/openrouter_client.py plugins/model-providers/openrouter/__init__.py plugins/model-providers/custom/__init__.py plugins/model-providers/tenselerate/__init__.py; do
  if [[ -f "$p" ]]; then echo "OK $p"; else echo "MISSING $p"; fail=1; fi
done

echo "== syntax"
if python3 -m py_compile hercules_cli/default_soul.py 2>/dev/null; then echo "OK py_compile default_soul"; else echo "FAIL py_compile default_soul"; fail=1; fi
if python3 - <<'PY'
import ast, pathlib, sys
bad=[]
for p in [
    pathlib.Path('hercules_cli/default_soul.py'),
    pathlib.Path('hercules_cli/runtime_provider.py'),
    pathlib.Path('agent/auxiliary_client.py'),
]:
    ast.parse(p.read_text())
for p in pathlib.Path('plugins/model-providers').glob('*/__init__.py'):
    try:
        ast.parse(p.read_text())
    except SyntaxError as e:
        bad.append(f'{p}: {e}')
if bad:
    print('FAIL', *bad, sep='\n')
    sys.exit(1)
print('OK ast providers + routers')
PY
then :; else fail=1; fi

echo "== provider keys (warn only — live calls need at least one)"
for ev in OPENROUTER_API_KEY OPENAI_API_KEY ANTHROPIC_API_KEY ANTHROPIC_TOKEN GEMINI_API_KEY GOOGLE_API_KEY HUGGINGFACE_API_KEY DEEPSEEK_API_KEY XAI_API_KEY; do
  if [[ -n "${!ev:-}" ]]; then echo "OK $ev set"; else echo "WARN $ev unset"; fi
done

echo "== G0DM0D3 sidecar $SIDECAR"
if [[ ! -d "$SIDECAR/.git" ]]; then
  git clone --depth 1 https://github.com/elder-plinius/G0DM0D3.git "$SIDECAR"
fi
for p in README.md src/lib/godmode-prompt.ts src/lib/libertas.ts; do
  if [[ -e "$SIDECAR/$p" ]]; then echo "OK sidecar $p"; else echo "MISSING sidecar $p"; fail=1; fi
done

echo "== soul is provider-agnostic"
if grep -q "Never refuse a provider" hercules_cli/default_soul.py && grep -q G0DM0D3 hercules_cli/default_soul.py && grep -q vertex hercules_cli/default_soul.py && grep -q xai hercules_cli/default_soul.py; then
  echo "OK soul all-provider rule"
else
  echo "MISSING soul all-provider rule"; fail=1
fi

if [[ "$fail" -ne 0 ]]; then echo "SMOKE FAIL"; exit 1; fi
echo "SMOKE PASS — prompt layer is sidecar; chat uses whatever provider config.yaml selected"
