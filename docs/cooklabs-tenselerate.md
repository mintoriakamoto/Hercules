# TENSELERATE as Hercules local provider

`hercules model` lists **TENSELERATE** first. Pick it. Empty API key is fine
(saved as the local placeholder `local`). Default endpoint is
`http://127.0.0.1:8080/v1`. If llama-server is up, the picker uses its
`/v1/models` list. If it is down, the model name stays `tenselerate`.

```bash
hercules model          # choose TENSELERATE
hercules doctor         # probes http://127.0.0.1:8080/v1/models — no API key
```

Non-interactive equivalent:

```bash
hercules config set model.provider tenselerate
hercules config set model.base_url http://127.0.0.1:8080/v1
hercules config set model.default tenselerate
hercules doctor
```

Start TENSELERATE first (`llama-server --port 8080`).

`hercules doctor` fails the llama-server check only when this provider (or
`custom` pointed at the same URL) is the configured model. Otherwise it warns.
This is the Cooklabs default, not Ollama-only.
