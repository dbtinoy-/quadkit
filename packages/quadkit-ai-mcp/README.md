# quadkit-ai-mcp

MCP Server for Quadkit Framework - Model Context Protocol server for AI agents

---

## Overview

Model Context Protocol (MCP) server and client implementation for the Quadkit Framework. Exposes tools, resources, and prompts to any MCP-compatible client — including Claude Desktop, Cursor, and custom AI agents — over SSE or stdio transports. Also provides MCP client connectivity for consuming external MCP servers. Zero-config usage starts with sensible defaults.


> Full documentation: [docs.quadkit.dev](https://docs.quadkit.dev)
## Install

```bash
uv add quadkit-ai-mcp
```

## Quick Start

```python
from quadkit import Application
from quadkit.di.module import Module, module

from quadkit.ai.mcp import MCPModule
from quadkit.ai.mcp.config import MCPConfig


@module(
    imports=[
        MCPModule.configure(
            config=MCPConfig(
                server_name="my-app",
                server_version="1.0.0",
                enable_sse=True,
                stdio_mode=False,
            )
        )
    ]
)
class AppModule(Module):
    pass


async with Application.boot(modules=[AppModule]) as app:
    # use app.container to resolve services
    ...
```

> **Note:** Full-module boot is currently limited — `MCPModule` registers handlers
> during the boot phase, which the container freeze (QK_ERR_DI_001) prevents.
> Use `Application.boot` for other modules; for MCP, resolve controllers/services
> directly from the container (`container.resolve(MyController)`) in tests.

## Configuration

> **Zero-config usage:** Call `MCPModule.configure()` with no arguments to use defaults.

### Option 1 — YAML file

```yaml
# application.yaml
ai_mcp:
  host: "0.0.0.0"
  port: 8080
  path: "/mcp"
  enable_sse: true
  server_name: "the optional provider"
  server_version: "1.0.0"
```

### Option 2 — Profiles + Environment Variables *(recommended)*

```bash
export QK_AI_MCP__ENABLED=true
export QK_AI_MCP__HOST=0.0.0.0
# Environment variables for each field
```

### Option 3 — Python

```python
from quadkit.ai.mcp.config import MCPConfig
from quadkit.ai.mcp import MCPModule

config = MCPConfig(
    enabled=True,
    host="0.0.0.0",
    port=8080,
    enable_sse=True,
    server_name="my-app",
)
MCPModule.configure(config)
```

### Config reference

| Field | Default | Env var | Description |
|-------|---------|---------|-------------|
| `enabled` | `True` | `QK_AI_MCP__ENABLED` | Enable the MCP server subsystem |
| `host` | `"0.0.0.0"` | `QK_AI_MCP__HOST` | Host to bind (HTTP transport) |
| `port` | `8080` | `QK_AI_MCP__PORT` | Port to bind (HTTP transport) |
| `path` | `"/mcp"` | `QK_AI_MCP__PATH` | URL path for MCP endpoint |
| `enable_sse` | `True` | `QK_AI_MCP__ENABLE_SSE` | Enable Server-Sent Events transport |
| `stdio_mode` | `False` | `QK_AI_MCP__STDIO_MODE` | Use stdio transport instead of HTTP |
| `server_name` | `"the optional provider"` | `QK_AI_MCP__SERVER_NAME` | MCP server name |
| `server_version` | `"1.0.0"` | `QK_AI_MCP__SERVER_VERSION` | MCP server version |
| `cors_origins` | `[]` | `QK_AI_MCP__CORS_ORIGINS` | CORS allowed origins |
| `max_request_size` | `1048576` | `QK_AI_MCP__MAX_REQUEST_SIZE` | Max request size (bytes) |
| `request_timeout` | `30.0` | `QK_AI_MCP__REQUEST_TIMEOUT` | Request timeout (seconds) |

## Module Factory Methods

| Method | Description |
|--------|-------------|
| `MCPModule.configure(config, controllers, services)` | Configure with explicit config |
| `MCPModule.from_services(services, include_methods)` | Auto-expose service methods as MCP tools |
| `MCPModule.stub()` | Minimal config for testing |
| `MCPClientModule.configure(connections)` | Configure MCP client connections |

## Key Features

- **Server**: Define tools using decorators (`@tool`, `@resource`, `@prompt`)
- **Controllers**: Group related tools via `MCPController`
- **Auto-expose**: Wire service methods as MCP tools
- **Transports**: SSE and stdio transport support
- **Built-in connectors**: Filesystem, GitHub, WebFetch, WebSearch, Slack, GoogleDrive, SQL
- **Client**: Connect to external MCP servers
- **Adapters**: Bridge to `quadkit-ai-agents` and `the optional provider`

## Testing

```python
async with Application.boot(modules=[MCPModule.stub()]) as app:
    # your test code
    ...
```

## Key Source Files

| File | What it contains |
|------|-----------------|
| `src/quadkit/ai/mcp/module.py` | `MCPModule.configure()`, `from_services()`, `stub()` |
| `src/quadkit/ai/mcp/config.py` | `MCPConfig` and connector config classes |
| `src/quadkit/ai/mcp/server/core.py` | `MCPServer` — protocol implementation |
| `src/quadkit/ai/mcp/client/module.py` | `MCPClientModule.configure()` |
| `src/quadkit/ai/mcp/transport/sse.py` | SSE transport (HTTP-based) |
| `src/quadkit/ai/mcp/transport/stdio.py` | Stdio transport (subprocess-based) |
| `src/quadkit/ai/mcp/controllers/base.py` | `MCPController` base class |
| `src/quadkit/ai/mcp/di/provider.py` | `MCPProvider` — registers MCP into DI |
