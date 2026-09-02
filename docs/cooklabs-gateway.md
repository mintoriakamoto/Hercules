# Cooklabs gateway

Nous managed Tool Gateway is off. First-party endpoints:

| Role | URL | Start |
|---|---|---|
| Hercules control / chat gateway | `http://127.0.0.1:8645` | `hercules gateway` |
| TENSELERATE inference | `http://127.0.0.1:8080/v1` | `bash TENSELERATE-/scripts/cooklabs_serve.sh MODEL.gguf 3060` |

```bash
python -m hercules_cli.cooklabs_gateway
python -m hercules_cli.cooklabs_gateway --json
```

Do not set `TOOL_GATEWAY_DOMAIN=nousresearch.com`. Vendor passthroughs stay inert unless you stand up your own `*_GATEWAY_URL`.
