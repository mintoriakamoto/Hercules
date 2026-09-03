# Hercules vs Hermes Agent

Upstream we studied: `NousResearch/hermes-agent` (MIT).
Product we ship: https://github.com/mintoriakamoto/Hercules

| Hermes | Hercules (better for Cooklabs) |
|---|---|
| `~/.hermes` + `HERMES_HOME` | `~/.hercules` + import from `~/.hermes` |
| `hermes update` → Nous GitHub | `hercules update` → mintoriakamoto/Hercules |
| Tool Gateway + Nous Portal | off; TENSELERATE `:8080` |
| Learning-loop skills in `~/.hermes/skills` | same loop in this tree + `hermes-imports/` |
| `hermes claw migrate` | `hercules claw migrate` |
| one agent | mesh: Hermes home + Claude + OpenCode + OpenClaw + venvs |

```bash
python -m hercules_cli.hermes
python -m hercules_cli.hermes migrate --dry-run
python -m hercules_cli.hermes migrate
hercules update
```
