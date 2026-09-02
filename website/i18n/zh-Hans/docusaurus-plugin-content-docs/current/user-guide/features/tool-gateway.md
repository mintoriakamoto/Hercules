---
title: "Tool Gateway"
description: "Cooklabs 自建工具网关。默认不走 Nous Portal。"
sidebar_label: "Tool Gateway"
sidebar_position: 2
---

# Tool Gateway

Cooklabs Hercules 不再默认连 Nous Tool Gateway。

- 推理：TENSELERATE `http://127.0.0.1:8080/v1`
- 工具：自己的 API Key，或自建 `TOOL_GATEWAY_DOMAIN`
- 代码里 `TOOL_GATEWAY_DOMAIN` 默认为空；`managed_nous_tools_enabled()` 永远为 false

自建网关才写 `.env`：

```bash
TOOL_GATEWAY_DOMAIN=your-domain.example.com
TOOL_GATEWAY_SCHEME=https
TOOL_GATEWAY_USER_TOKEN=your-token
```

不要写 `TOOL_GATEWAY_DOMAIN=nousresearch.com`。
