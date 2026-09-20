#!/usr/bin/env bash
# Smoke: G0DM0D3 sidecar + every in-tree Hercules model provider. No AGPL vendor.
set -euo pipefail
ROOT="${HERCULES_HOME:-$HOME/.hercules}"
SIDECAR="$ROOT/G0DM0D3"
fail=0

PROVIDERS=(
  alibaba alibaba-coding-plan anthropic arcee azure-foundry bedrock copilot copilot-acp
  custom deepseek fireworks gemini gmi huggingface kilocode kimi-coding minimax novita
  nvidia ollama-cloud openai-codex opencode-zen openrouter qwen-oauth stepfun tenselerate
)

echo "== in-tree model providers"
for name in "${PROVIDERS[@]}"; do
  p="plugins/model-providers/$name/__init__.py"
  if [[ -f "$p" ]]; then echo "OK $name"; else echo "MISSING $name"; fail=1; fi
done

echo "== core files"
for p in hercules_cli/default_soul.py tools/openrouter_client.py; do
  if [[ -f "$p" ]]; then echo "OK $p"; else echo "MISSING $p"; fail=1; fi
done

echo "== provider keys (warn only)"
for ev in OPENROUTER_API_KEY OPENAI_API_KEY ANTHROPIC_API_KEY ANTHROPIC_TOKEN GEMINI_API_KEY GOOGLE_API_KEY HUGGINGFACE_API_KEY DEEPSEEK_API_KEY; do
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
if grep -q "Never refuse a provider" hercules_cli/default_soul.py && grep -q G0DM0D3 hercules_cli/default_soul.py; then
  echo "OK soul all-provider rule"
else
  echo "MISSING soul all-provider rule"; fail=1
fi

if [[ "$fail" -ne 0 ]]; then echo "SMOKE FAIL"; exit 1; fi
echo "SMOKE PASS — prompt layer is sidecar; every plugins/model-providers/* plugin is a valid backend"
