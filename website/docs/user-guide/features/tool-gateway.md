---
title: "Tool Gateway"
description: "Every tool built in. Web search, image generation, TTS, and cloud browsers — routed through the Tool Gateway with no extra API keys."
sidebar_label: "Tool Gateway"
sidebar_position: 2
---

# Tool Gateway

**Every tool, one gateway.**

The Tool Gateway routes Hercules' tool calls — web search, image generation, text-to-speech, and cloud browser automation — through managed infrastructure, so you don't have to sign up with Firecrawl, FAL, OpenAI, Browser Use, or anyone else just to make your agent useful.

## What's included

| | Tool | What you get |
|---|---|---|
| 🔍 | **Web search & extract** | Agent-grade web search and full-page extraction via Firecrawl. No rate limits to worry about — the gateway handles scaling. |
| 🎨 | **Image generation** | Nine models under one endpoint: **FLUX 2 Klein 9B**, **FLUX 2 Pro**, **Z-Image Turbo**, **Nano Banana Pro** (Gemini 3 Pro Image), **GPT Image 1.5**, **GPT Image 2**, **Ideogram V3**, **Recraft V4 Pro**, **Qwen Image**. Pick per-generation with a flag, or let Hercules default to FLUX 2 Klein. |
| 🔊 | **Text-to-speech** | OpenAI TTS voices wired into the `text_to_speech` tool. Drop voice notes into Telegram, generate audio for pipelines, narrate anything. |
| 🌐 | **Cloud browser automation** | Headless Chromium sessions via Browser Use. `browser_navigate`, `browser_click`, `browser_type`, `browser_vision` — all the agent-driving primitives, no Browserbase account required. |

Use any combination — run the gateway for web and images while keeping your own ElevenLabs key for TTS, or route everything through the gateway.

## Why it's here

Building an agent that can actually *do things* means stitching together 5+ API subscriptions — each with their own signup, rate limits, billing, and quirks. The gateway collapses that into one path:

- **One signup.** No Firecrawl, FAL, Browser Use, or OpenAI audio accounts to manage.
- **No per-tool API keys.** The gateway fronts every tool, so you don't wire up each backend yourself.
- **Same quality.** Same backends the direct-key route uses — just fronted by the gateway.

Bring your own keys anytime — per-tool, whenever you want to. The gateway isn't a lock-in, it's a shortcut.

## Get started

Enable the gateway per-tool with `hercules tools` — pick the managed backend for any tool you want:

```bash
hercules tools              # Enable the gateway per-tool
```

`hercules tools` lists the managed backends (Web search, Image, Video, TTS, Browser) alongside any direct-key providers. Select a managed backend for a tool and Hercules routes that tool through the gateway; leave the others on your own keys. This turns on just the tools you pick, one at a time.

Check what's active at any time:

```bash
hercules tools --summary    # Current routing per tool
hercules status             # Full system status (Tool Gateway is one section)
```

`hercules status` shows a section like:

```
◆ Tool Gateway
  Web tools       ✓ active via gateway
  Image gen       ✓ active via gateway
  TTS             ✓ active via gateway
  Browser         ○ active via Browser Use key
```

Tools marked "active via gateway" are going through the gateway. Anything else is using your own keys.

## Mix and match

The gateway is per-tool. Turn it on for just what you want:

- **All tools through the gateway** — easiest; one setup, done.
- **Gateway for web + images, bring your own TTS** — keep your ElevenLabs voice, let the gateway handle the rest.
- **Gateway only for things you don't have keys for** — "I already pay for Browserbase, but I don't want a Firecrawl account" works fine.

Switch any tool at any time via:

```bash
hercules tools          # Interactive picker for each tool category
```

Select the tool, pick the managed gateway backend as the provider (or any direct provider you prefer). No config editing required.

## Using individual image models

Image generation defaults to FLUX 2 Klein 9B for speed. Override per-call by passing the model ID to the `image_generate` tool:

| Model | ID | Best for |
|---|---|---|
| FLUX 2 Klein 9B | `fal-ai/flux-2/klein/9b` | Fast, good default |
| FLUX 2 Pro | `fal-ai/flux-2-pro` | Higher fidelity FLUX |
| Z-Image Turbo | `fal-ai/z-image/turbo` | Stylized, fast |
| Nano Banana Pro | `fal-ai/nano-banana-pro` | Google Gemini 3 Pro Image |
| GPT Image 1.5 | `fal-ai/gpt-image-1.5` | OpenAI image gen, text+image |
| GPT Image 2 | `fal-ai/gpt-image-2` | OpenAI latest |
| Ideogram V3 | `fal-ai/ideogram/v3` | Strong prompt adherence + typography |
| Recraft V4 Pro | `fal-ai/recraft/v4/pro/text-to-image` | Vector-style, graphic design |
| Qwen Image | `fal-ai/qwen-image` | Alibaba multimodal |

The set evolves — `hercules tools` → Image Generation shows the current live list.

---

## Configuration reference

Most users never need to touch this — `hercules model` and `hercules tools` cover every workflow interactively. This section is for writing config.yaml directly or scripting setups.

### Per-tool `use_gateway` flag

Each tool's config block takes a `use_gateway` boolean:

```yaml
web:
  backend: firecrawl
  use_gateway: true

image_gen:
  use_gateway: true

tts:
  provider: openai
  use_gateway: true

browser:
  cloud_provider: browser-use
  use_gateway: true
```

Precedence: `use_gateway: true` routes through the gateway regardless of any direct keys in `.env`. `use_gateway: false` (or absent) uses direct keys if available and only falls back to the gateway when none exist.

### Disabling the gateway

```yaml
web:
  use_gateway: false   # Hercules now uses FIRECRAWL_API_KEY from .env
```

`hercules tools` automatically clears the flag when you pick a non-gateway provider, so this usually happens for you.

### Self-hosted gateway (advanced)

Running your own gateway? Override endpoints in `~/.hercules/.env`:

```bash
TOOL_GATEWAY_DOMAIN=your-domain.example.com
TOOL_GATEWAY_SCHEME=https
TOOL_GATEWAY_USER_TOKEN=your-token        # your gateway user token
FIRECRAWL_GATEWAY_URL=https://...         # override one endpoint specifically
```

These knobs exist for custom infrastructure setups (enterprise deployments, dev environments). Most users never set them.

## FAQ

### Does it work with Telegram / Discord / the other messaging gateways?

Yes. Tool Gateway operates at the tool-execution layer, not the CLI. Every interface that can call a tool — CLI, Telegram, Discord, Slack, IRC, Teams, the API server, anything — benefits from it transparently.

### What if a gateway tool stops working?

Swap in a direct API key for that tool via `hercules tools`. Hercules shows a clear error when a gateway tool can't run, so you know which key to add.

### Can I see which tools are using the gateway?

Yes — `hercules tools --summary` and `hercules status` show the current routing per tool.

### Is Modal (serverless terminal) included?

Modal is a separate optional terminal backend, not part of the default Tool Gateway bundle. Configure it via `hercules setup terminal` or directly in `config.yaml` when you want a remote sandbox for shell execution.

### Do I need to delete my existing API keys when I enable the gateway?

No — keep them in `.env`. When `use_gateway: true`, Hercules skips direct keys and uses the gateway. Flip the flag back to `false` and your keys become the source again. The gateway isn't a lock-in.
