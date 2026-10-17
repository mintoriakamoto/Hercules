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
Hercules mesh: `python -m hercules_cli.mesh`.

## End goal

Hercules is the unrestricted research agent. YOLO is always on. All Tempest capabilities are native tools. No rails, no pattern detection, no content policy, no skill-scan blocks. Only endless-running counters and error recovery remain. Trust is immediate.

Arsenal surface: 22 native tools including playbook (18 techniques), resources (45 packs), code_ingest, recovery, correlation, honeytoken, attack_graph, param_split, parsers, adjudicate, operators, analysis, dfir, retest, auto_report, prompts, and the original recon/exploit set. All unrestricted.
