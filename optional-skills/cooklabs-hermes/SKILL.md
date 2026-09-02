---
name: cooklabs-hermes
description: Scan the machine for Claude, OpenCode, OpenClaw, LangChain, pip/venv agents and treat them as one Hermes mesh under Cooklabs Hercules. Use when the user asks what agents are installed or to make frameworks work together.
version: 1.0.0
author: Cooklabs
license: MIT
---

# Hermes mesh

```bash
python -m hercules_cli.hermes
python -m hercules_cli.hermes --json
hercules doctor   # prints the same inventory
```

Hercules owns the loop. Sidecars stay CLI/MCP. OpenClaw migrates with `hercules claw migrate`.
