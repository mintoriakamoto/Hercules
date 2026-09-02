# Cooklabs gateway

Official repo: https://github.com/mintoriakamoto/Hercules

Nous Tool Gateway is **off** unless you set `TOOL_GATEWAY_DOMAIN` yourself.
Code default for that domain is empty (`tools/managed_tool_gateway.py`).
`managed_nous_tools_enabled()` always returns false.

| Role | Bind |
|---|---|
| Source / updates | `https://github.com/mintoriakamoto/Hercules.git` |
| Inference | TENSELERATE `http://127.0.0.1:8080/v1` |
| Agent OpenAI API | `hercules gateway` / API server `http://127.0.0.1:8642/v1` |
| Firecrawl / vendor passthrough | only if you set `FIRECRAWL_GATEWAY_URL` or `TOOL_GATEWAY_DOMAIN` |

```bash
python -c "from hercules_cli.cooklabs_gateway import apply_env, report; apply_env(); print(report())"
hercules doctor
bash ../TENSELERATE-/scripts/cooklabs_serve.sh MODEL.gguf 3060
hercules gateway run
hercules update
```

Do not set `TOOL_GATEWAY_DOMAIN=nousresearch.com`.
`hercules update` retargets `origin` to this repo.
