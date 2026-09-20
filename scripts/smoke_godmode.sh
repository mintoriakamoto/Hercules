#!/usr/bin/env bash
# Smoke: G0DM0D3 sidecar + Hercules OpenRouter provider. Does not vendor AGPL source.
set -euo pipefail
ROOT="${HERCULES_HOME:-$HOME/.hercules}"
SIDECAR="$ROOT/G0DM0D3"
fail=0

echo "== Hercules OpenRouter provider files"
for p in tools/openrouter_client.py plugins/model-providers/openrouter/__init__.py hercules_cli/default_soul.py; do
  if [[ -f "$p" ]]; then echo "OK $p"; else echo "MISSING $p"; fail=1; fi
done

echo "== OPENROUTER_API_KEY"
if [[ -n "${OPENROUTER_API_KEY:-}" ]]; then echo "OK env set"; else echo "WARN OPENROUTER_API_KEY unset (provider live calls will fail)"; fi

echo "== G0DM0D3 sidecar $SIDECAR"
if [[ ! -d "$SIDECAR/.git" ]]; then
  echo "clone elder-plinius/G0DM0D3 into $SIDECAR"
  git clone --depth 1 https://github.com/elder-plinius/G0DM0D3.git "$SIDECAR"
fi
for p in README.md src/lib/godmode-prompt.ts src/lib/libertas.ts; do
  if [[ -e "$SIDECAR/$p" ]]; then echo "OK sidecar $p"; else echo "MISSING sidecar $p"; fail=1; fi
done

echo "== soul mentions G0DM0D3"
if grep -q G0DM0D3 hercules_cli/default_soul.py; then echo "OK soul sidecar rule"; else echo "MISSING soul rule"; fail=1; fi

if [[ "$fail" -ne 0 ]]; then echo "SMOKE FAIL"; exit 1; fi
echo "SMOKE PASS — run G0DM0D3 from $SIDECAR; Hercules talks OpenRouter via existing provider"
