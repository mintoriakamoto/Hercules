---
sidebar_position: 0
title: "Run Nemotron 3 Ultra free in Hercules Agent"
description: "Try NVIDIA Nemotron 3 Ultra free via OpenRouter — with day 0 support in Hercules Agent"
---

# Run Nemotron 3 Ultra free in Hercules Agent

Nous Research has been inducted into the **Nemotron Coalition** of leading AI labs working with **NVIDIA** to advance open frontier foundation models. **Nemotron 3 Ultra** has day 0 support in Hercules Agent, and you can run it free via [OpenRouter](https://openrouter.ai)'s no-cost tier. Follow the instructions below to try the model in your Hercules Agent today.

:::info Free tier
The `nvidia/nemotron-3-ultra:free` variant runs on the no-cost tier. The `:free` tag is what keeps it free — pick that exact variant.
:::

Pick whichever install fits you. The **desktop app** is the easiest — no terminal required. If you live in a terminal, the **command-line** install is right below it.

## Option A — Desktop app (recommended)

The simplest path: a one-click installer with a guided, point-and-click setup. No terminal needed.

### 1. Download and install

[Download the Hercules Desktop installer](https://github.com/mintoriakamoto/Hercules/) for macOS or Windows, then open it. On first launch it finishes setting itself up (usually under a minute).

### 2. Connect a provider

When the app opens, you'll see a "Let's get you set up" screen. Choose a provider that serves this model — [OpenRouter](https://openrouter.ai) offers the free `:free` variant. Add your OpenRouter API key (create a free account at [openrouter.ai](https://openrouter.ai) if you don't have one) and the app connects.

### 3. Pick the free Nemotron 3 Ultra model

After connecting, the app shows a **Default model** card. Click **Change**, search for **nemotron 3 ultra**, and select the variant tagged **Free tier**:

```
nvidia/nemotron-3-ultra:free
```

The `:free` tag is what keeps it on the no-cost tier — pick that variant.

### 4. Start chatting

Click **Start chatting**. That's it — you're talking to Nemotron 3 Ultra, free.

## Option B — Command line

Prefer the terminal?

### 1. Install Hercules Agent

On macOS/Linux/WSL2/Android, run

```bash
curl -fsSL https://raw.githubusercontent.com/mintoriakamoto/Hercules/main/scripts/install.sh | bash
```

On Windows, run

```powershell
iex (irm https://raw.githubusercontent.com/mintoriakamoto/Hercules/main/scripts/install.ps1)
```

Prefer to review first? Download [`install.sh`](https://raw.githubusercontent.com/mintoriakamoto/Hercules/main/scripts/install.sh), inspect it, then run it.

After it finishes, reload your shell:

```bash
source ~/.bashrc   # or source ~/.zshrc
```

### 2. Add an OpenRouter API key

Create a free [OpenRouter](https://openrouter.ai) account (or sign in) and generate an API key, then add it to `~/.hercules/.env`:

```bash
echo 'OPENROUTER_API_KEY=sk-or-v1-...' >> ~/.hercules/.env
```

A single OpenRouter key covers this model and 300+ others.

### 3. Run setup

```bash
hercules setup
```

Follow the prompts to finish configuring Hercules.

### 4. Select the free Nemotron 3 Ultra model

From the model list, select:

```
nvidia/nemotron-3-ultra:free
```

The `:free` tag is what keeps it on the no-cost tier, so make sure you pick that variant.

### 5. Start chatting

Complete the remaining Quick Setup prompts, then run:

```bash
hercules
```

That's it — you're talking to Nemotron 3 Ultra, free.

## Switching to it later

Already set up with another model?

- **Desktop app:** open the model picker, search for **nemotron 3 ultra**, and select the **Free tier** variant.
- **CLI / TUI:** switch any time from inside a session with `/model nvidia/nemotron-3-ultra:free`, or run `/model` to open the picker and choose it from the list.

## Troubleshooting

- **Don't see the model in the list?** Make sure your provider credentials are configured and that you're on a plan that exposes the model. Run `hercules model` to re-check your provider setup.
- **Picked the wrong variant?** Re-select `nvidia/nemotron-3-ultra:free` — the `:free` suffix is required to stay on the no-cost tier.
- **Browser didn't open / you're on a remote host (CLI)?** See [OAuth over SSH / Remote Hosts](/guides/oauth-over-ssh) for port-forwarding workarounds.

## See also

- **[Desktop App](/user-guide/desktop)** — The native one-click app (macOS, Windows, Linux)
- **[AI Providers](/integrations/providers)** — Set up OpenRouter and other model providers
- **[Quickstart](/getting-started/quickstart)** — Install-to-chat in under 5 minutes
