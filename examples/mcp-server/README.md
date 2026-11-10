# MCP Server Demo

A focused, runnable example of **`quadkit-ai-mcp`**. An `MCPController`
exposes incident tools (`@tool`), operational runbooks (`@resource`), and
triage prompt templates (`@prompt`) through `MCPModule` and `MCPServer`, with
an HTTP bridge so you can inspect capabilities and send JSON-RPC 2.0 requests
from a browser or `curl`.

## What you'll learn

1. `MCPController` + `@tool` / `@resource` / `@prompt` — group MCP capabilities
   with auto-generated JSON Schema input definitions
2. `MCPModule.configure(controllers=[...])` — wire handlers and `MCPServer`
   into the QuadKit DI container
3. Fail-closed authorization — `MCPAuthorizerProtocol` gates every
   post-handshake JSON-RPC method cleanly
4. `MCPServer.handle_message` — protocol-compliant JSON-RPC 2.0 handshake
   (`initialize` → `notifications/initialized`) and method dispatch
5. `Result` → RFC-9457 `ProblemDetail` — unknown tool calls return a structured
   `404` problem response

## Read in order

| # | File | What you learn |
|---|------|----------------|
| 1 | `src/mcp_side/app.py` | `MCPModule` + `WebModule` composition root |
| 2 | `src/mcp_side/mcp/runbooks.py` | `MCPController` with `@tool`, `@resource`, and `@prompt` |
| 3 | `src/mcp_side/services/bridge.py` | Handshake + JSON-RPC 2.0 dispatch against `MCPServer` |
| 4 | `src/mcp_side/controllers/api.py` | Thin HTTP adapter (`GET /mcp/capabilities`, `POST /mcp/rpc`, `POST /mcp/tools/{name}`) |
| 5 | `tests/` | Real ASGI round trips over `MCPServer` — no mocks |

## Run it

```bash
PYTHONPATH=examples/mcp-server/src uv run python -m mcp_side   # :8133
```

- `GET /mcp/capabilities` — list registered MCP tools, resources, and prompts
- `POST /mcp/tools/lookup_incident` — invoke a tool with `{"incident_id": "INC-101"}`
- `POST /mcp/rpc` — send a raw JSON-RPC 2.0 MCP message (`tools/list`, `resources/read`, `prompts/get`)

## Tests

```bash
uv run pytest examples/mcp-server/tests
```
