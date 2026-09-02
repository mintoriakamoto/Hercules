---
sidebar_position: 3
title: "Cooklabs gateway env"
description: "Official defaults. The old Nous rows in environment-variables.md are stale."
---

# Cooklabs gateway environment

Runtime source of truth is `tools/managed_tool_gateway.py` and `hercules_cli/cooklabs_gateway.py`.

| Variable | Actual default |
|----------|----------------|
| `TOOL_GATEWAY_DOMAIN` | **empty** — not `nousresearch.com` |
| `TOOL_GATEWAY_SCHEME` | `https` only if you set a domain; local inference uses `http` |
| `TOOL_GATEWAY_USER_TOKEN` | unset |
| `OPENAI_BASE_URL` / `TENSELERATE_BASE_URL` | `http://127.0.0.1:8080/v1` |
| `NOUS_BASE_URL` / `HERCULES_PORTAL_BASE_URL` | unused |

The long [Environment Variables](./environment-variables.md) page still has a leftover "Nous Tool Gateway" table. Ignore those four rows.
