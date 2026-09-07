# 🦁 Hercules Quick Start Guide

Welcome to Hercules! This guide will get you up and running in 5 minutes.

## What is Hercules?

Hercules is a self-improving AI agent that:
- 🧠 **Learns** from every conversation and improves over time
- 📱 **Works everywhere** - CLI, Telegram, Discord, Slack, mobile, web
- 🔓 **Respects freedom** - You own your data, choose your model, deploy anywhere
- ⚡ **Moves fast** - Production-ready with enterprise-grade reliability
- 🔒 **Keeps you safe** - Comprehensive security and privacy controls

**Tagline:** *AI That Learns. AI That Grows. AI That Remembers.*

## Installation (Choose Your Path)

### Path 1: Easiest (Recommended for Most Users)

**Linux, macOS, WSL2, or Android Termux:**
```bash
curl -fsSL https://raw.githubusercontent.com/mintoriakamoto/Hercules/main/scripts/install.sh | bash
```

**Windows (PowerShell):**
```powershell
iex (irm https://raw.githubusercontent.com/mintoriakamoto/Hercules/main/scripts/install.ps1)
```

After installation:
```bash
source ~/.bashrc    # macOS: source ~/.zshrc
hercules
```

### Path 2: From Source (For Developers)

```bash
git clone https://github.com/mintoriakamoto/Hercules
cd Hercules
pip install -e ".[dev]"
hercules
```

### Path 3: Docker (For Deployment)

```bash
# Download configuration
curl -O https://raw.githubusercontent.com/mintoriakamoto/Hercules/main/docker-compose.yml

# Start Hercules
HERCULES_UID=$(id -u) HERCULES_GID=$(id -g) docker compose up -d

# View logs
docker logs -f hercules
```

### Path 4: Native Windows

Use the PowerShell installer above. It handles everything:
- Downloads and installs Python 3.11
- Sets up uv package manager
- Installs all dependencies
- Creates portable Git Bash environment
- No admin access required

## Your First Conversation

### Start the CLI
```bash
hercules
```

You'll see:
```
🦁 Hercules Agent
Connected to Claude 3.5 Sonnet (OpenAI)

Type /help for commands
> _
```

### Try These Commands

**Simple chat:**
```
> What are the key features of Hercules?
```

**Use a tool:**
```
> Search GitHub for "python ai agents" and summarize
```

**Create a quick task:**
```
> Plan my day tomorrow: morning meeting, afternoon coding session, evening rest
```

**Switch models:**
```
/model list           # See available models
/model gpt-4          # Switch to GPT-4
/model claude         # Switch to Claude
```

**Create a skill:**
```
> Create a skill: "summarize-daily-news" that finds and summarizes top 5 news items
```

## Configuration

### API Keys

Hercules supports multiple AI providers. Set up your preferred one:

**Claude (Anthropic):**
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
hercules
```

**OpenAI:**
```bash
export OPENAI_API_KEY="sk-..."
hercules
```

**Others:** See [integrations documentation](website/docs/integrations/)

### Environment Setup

Create `.env` file in `~/.hercules/`:
```bash
# Your preferred model provider
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Platform integrations
SLACK_BOT_TOKEN=xoxb-...
DISCORD_TOKEN=...
TELEGRAM_BOT_TOKEN=...

# Optional: Custom storage
HERCULES_HOME=~/.hercules
```

## Connecting Platforms

### Telegram
```bash
/setup telegram
# Follow prompts to get bot token
# Add @YourBotName to start chatting
```

### Discord
```bash
/setup discord
# Creates invite link
# Add bot to your server
```

### Slack
```bash
/setup slack
# Provides OAuth link
# Complete setup in Slack
```

### CLI (Default)
Works out of the box - just type `hercules`

## Creating Skills

Skills are reusable automations that Hercules learns from your tasks.

### Auto-Create from Conversation
```
> I need to process customer feedback files daily. 
> Read them, extract sentiment, save to CSV
```

Hercules will:
1. Help you complete this task
2. Recognize the pattern
3. Create a reusable skill automatically
4. Suggest scheduling it

### Manual Skill Creation
```bash
hercules skill create --name summarize-documents \
  --description "Read docs and create executive summary" \
  --input "file_path" \
  --output "summary"
```

### Use Your Skills
```
> Use skill:summarize-documents on report.pdf
> schedule skill:process-feedback daily at 9am
```

## Key Commands

```bash
# Conversation management
/history              # Show past conversations
/search <query>       # Full-text search across memory
/export              # Export conversations
/clear               # Start fresh

# Model & provider
/model list          # Available models
/model <name>        # Switch model
/settings            # View configuration

# Skill management
/skills              # List your skills
/skill create        # Create new skill
/skill delete <name> # Remove skill

# Platform integration
/setup <platform>    # Add Telegram/Discord/Slack
/integrations        # View connected platforms

# System
/help                # Show command help
/status              # System status
/update              # Check for updates
/quit                # Exit Hercules
```

## Learning & Documentation

### Quick Resources
- **Installation Issues:** [INSTALL.md](INSTALL.md)
- **Full Docs:** [website/docs/](website/docs/)
- **Our Vision:** [VISION.md](VISION.md)
- **Community:** [CULTURE.md](CULTURE.md)

### Video Tutorials
- Getting Started (5 min)
- Creating Your First Skill (10 min)
- Multi-Platform Setup (15 min)
- Advanced Workflows (30 min)

[Watch on YouTube](https://youtube.com/@HerculesAgent)

### Written Guides
- [Installation Guide](INSTALL.md)
- [User Guide](website/docs/user-guide/)
- [Skill Development](website/docs/developer-guide/skills.md)
- [API Reference](website/docs/developer-guide/api.md)

## Troubleshooting

### "Command not found: hercules"
**Solution:** Reload your shell
```bash
source ~/.bashrc      # Linux/WSL
source ~/.zshrc       # macOS
exec $SHELL           # All platforms
```

### "No API key found"
**Solution:** Set environment variable
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
# Or create .env file in ~/.hercules/
```

### "Connection timeout"
**Solution:** Check network and proxy settings
```bash
# Test connection
curl https://api.openai.com/v1/models

# Check logs
hercules --debug
```

### "Permission denied" (Linux/macOS)
**Solution:** Fix permissions
```bash
chmod +x ~/.hercules/bin/hercules
```

### Still stuck?
1. Check [GitHub Issues](https://github.com/mintoriakamoto/Hercules/issues)
2. Ask in [Discussions](https://github.com/mintoriakamoto/Hercules/discussions)
3. Join [Discord community](https://discord.gg/hercules-ai)

## Next Steps

### For Power Users
- [Advanced Workflows](website/docs/guides/workflows.md)
- [Custom Integration Guide](website/docs/developer-guide/integrations.md)
- [Performance Tuning](docs/HARDWARE_CONFIGURATION.md)

### For Developers
- [Skill Development SDK](website/docs/developer-guide/skills.md)
- [Plugin Architecture](website/docs/developer-guide/plugins.md)
- [Contributing Guide](CONTRIBUTING.md)

### For Enterprises
- [Enterprise Features](website/docs/enterprise/)
- [Deployment Guide](website/docs/enterprise/deployment.md)
- [Contact Sales](mailto:enterprise@mintoriakamoto.com)

## Community

Join thousands of users and developers:

- **GitHub:** [mintoriakamoto/Hercules](https://github.com/mintoriakamoto/Hercules)
- **Discussions:** [Community Hub](https://github.com/mintoriakamoto/Hercules/discussions)
- **Discord:** [Live Chat](https://discord.gg/hercules-ai)
- **Twitter:** [@HerculesAgent](https://twitter.com/HerculesAgent)
- **Email:** community@mintoriakamoto.com

## What's Next?

Hercules is constantly evolving. Upcoming features:

- 🎯 **Q1 2025:** Advanced memory and learning
- 📱 **Q2 2025:** Native mobile apps (iOS/Android)
- 🌍 **Q3 2025:** Multi-region deployment
- 👥 **Q4 2025:** Team collaboration features

Check [ROADMAP.md](ROADMAP.md) for full details.

---

## Key Concepts

### Memory
Hercules remembers conversations and learns patterns, creating an adaptive model of your preferences and workflow.

### Skills
Reusable automations that Hercules creates from complex tasks and refines over time.

### Platforms
One Hercules instance works everywhere—CLI, Telegram, Discord, Slack, or your custom integration.

### Autonomy
You control which models to use, where to run Hercules, and how your data is stored.

---

## One More Thing

Everything in Hercules is built with care:

✅ **Production Ready** - Comprehensive error handling and security
✅ **Well Tested** - 95%+ test coverage on critical paths  
✅ **Documented** - Clear guides for every feature
✅ **Secure** - Your data is your own, encrypted by default
✅ **Free** - Open source MIT licensed
✅ **Supportive** - Active community and core team

Ready to experience the future of AI agents?

```bash
hercules
```

**🦁 Hercules - AI That Learns. AI That Grows. AI That Remembers.**

---

*Last Updated: 2026-09-07*
*Version: 1.0 - Quick Start Guide*

**Questions?** Join our [community](https://github.com/mintoriakamoto/Hercules/discussions) or check [ABOUT.md](ABOUT.md) to learn more about Hercules.
