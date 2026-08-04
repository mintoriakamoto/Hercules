# Local-only mode — running Hercules with no cloud providers

Hercules can run entirely against local inference servers, never sending a
prompt to a hosted API. This is for private, offline, or self-hosted
deployments where cloud providers are not acceptable.

## What it does

Setting `providers.local_only: true` in `config.yaml` makes Hercules **refuse
to resolve any non-local provider**. Every model call funnels through one
resolver (`hercules_cli/runtime_provider.py::resolve_runtime_provider`); with
the flag on, that resolver checks the *endpoint it resolved to* and raises a
clear, actionable error if it is not local — before any request is sent.

The check is on the **endpoint, not the provider name**. A `custom` provider
pointed at `https://api.openai.com` is rejected exactly like the `openai-api`
provider is. You cannot accidentally leak to a cloud host by mislabelling it.

### What counts as "local"

An endpoint is local when its host is:

- a loopback address — `localhost`, `127.0.0.1`, `::1`, `0.0.0.0`;
- a private LAN address — `10.x`, `172.16–31.x`, `192.168.x`, or link-local;
- a Tailscale/headscale CGNAT address — `100.64.0.0/10`;
- an mDNS / internal name — `*.local`, `*.internal`, `*.lan`, `*.localdomain`;
- a bare single-label hostname — e.g. `gpu-box`, or a Docker service name.

Anything with a public, dotted hostname (`api.openai.com`, `openrouter.ai`,
`ollama.com`) is treated as cloud and rejected. Note **Ollama *Cloud*
(`ollama.com`) is cloud** — only a local Ollama daemon qualifies.

## Enabling it

```bash
hercules config set providers.local_only true
```

Then point the model at a local backend. Any OpenAI-compatible server works.

### Ollama

```bash
hercules config set model.provider custom
hercules config set model.base_url http://localhost:11434/v1
hercules config set model.default qwen2.5-coder:32b
```

### vLLM

```bash
# vllm serve Qwen/Qwen2.5-Coder-32B-Instruct --port 8000
hercules config set model.provider custom
hercules config set model.base_url http://localhost:8000/v1
```

### llama.cpp (`llama-server`)

```bash
# llama-server -m model.gguf --port 8080 -c 32768
hercules config set model.provider custom
hercules config set model.base_url http://localhost:8080/v1
```

### ExLlamaV2 (via TabbyAPI)

```bash
# TabbyAPI exposes an OpenAI-compatible endpoint on :5000 by default
hercules config set model.provider custom
hercules config set model.base_url http://localhost:5000/v1
```

### LM Studio

Use the built-in `lmstudio` provider, or a `custom` endpoint at
`http://localhost:1234/v1`.

A GPU box reachable over your LAN or Tailscale works too — e.g.
`http://gpu-box:8000/v1` or `http://100.101.102.103:8000/v1`.

## Behaviour when it blocks

If a cloud provider is resolved while the mode is on, the run stops with:

```
Local-only mode is on (providers.local_only), but the endpoint resolved for
provider 'openai-api' is not local:
    https://api.openai.com/v1
...
```

The error names the offending endpoint and lists the fix. Because
`LocalOnlyModeError` subclasses `AuthError`, any code path that already treats
an unresolved provider as a fatal configuration problem handles this the same
way.

## What this is and isn't

- **It is** a hard runtime gate: cloud endpoints cannot be reached while it is
  on, whatever the model catalog or provider config says.
- **It is not** a code removal. The cloud provider adapters remain in the tree,
  dormant and unreachable under this flag; turning the flag off restores them.
  This keeps the change reversible and the test suite intact.
- **It does not** make responses smarter. Local models are typically less
  capable than frontier cloud models, and speed depends on your hardware. The
  win here is privacy, cost, offline operation, and no vendor lock-in — not raw
  model strength.

## Disabling it

```bash
hercules config set providers.local_only false
```
