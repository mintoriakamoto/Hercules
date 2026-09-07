# Cooklabs overlay

This repository is the **Hercules** product under Cooklabs.
Canonical map: https://github.com/mintoriakamoto/Cooklabs

Not Nous Research. Derived from their MIT Hercules Agent. We keep the license.

## Gateways (ours)

- Inference: TENSELERATE `http://127.0.0.1:8080/v1`
- Agent API: `hercules gateway run` → `http://127.0.0.1:8642/v1`
- Tool Gateway domain: **unset**. Code no longer defaults to `nousresearch.com`.
  `managed_nous_tools_enabled()` is always false.

See `docs/cooklabs-gateway.md` and `hercules_cli/cooklabs_gateway.py`.

Personas Read / Coder / Developer: `optional-skills/cooklabs-personas/`.
Hermes mesh: `python -m hercules_cli.hermes`.
