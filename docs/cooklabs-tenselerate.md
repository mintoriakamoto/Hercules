# TENSELERATE as Hercules local provider

```bash
hercules config set model.provider custom
hercules config set model.base_url http://127.0.0.1:8080/v1
hercules config set model.name tenselerate
hercules doctor
```

Start TENSELERATE first (`llama-server --port 8080` plus `svmi-plan.py` flags for 3060 / 2080ti / 1660ti).

This is the Cooklabs default, not Ollama-only.
