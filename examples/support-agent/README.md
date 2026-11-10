# Support Agent Demo

> Module name: `support_agent` — run with `PYTHONPATH=examples/support-agent/src uv run python -m support_agent`

Demonstrates the **AI agents subsystem** from `quadkit-ai-agents` through a
browser: pick a scripted scenario, watch the ReAct agent reason step-by-step,
call tools (order lookup, refund calculation, KB search), and see the traced
response with token counts and timing.

Fully offline against a scripted LLM — no API keys, no network. The agent
runs for real (tools get called, the strategy parser drives the loop) while
model output stays byte-stable across runs.

## Quadkit concepts used

| Concept | Where in this demo | Your app |
|---------|-------------------|----------|
| Composition root | `app.py` | Replace controllers/providers list |
| Module pattern | `AgentsModule`, `WebModule` | Add your own modules |
| Provider lifecycle | `di/provider.py` | Replace with your registrations |
| Result<T,E> pattern | `controllers/api.py` | Return Result from handlers |
| Agent builder | `services/support_service.py` | Build agents with `AgentBuilder` |
| `@tool` decorator | `tools.py` | Wrap functions as agent tools |
| ReAct strategy | `repository/scenarios.py` | Scripted completions drive the loop |
| Scripted LLM | `repository/scripted_llm.py` | Deterministic stand-in for `LLMClientProtocol` |

## What it shows

| Piece | Where | Quadkit API used |
|-------|-------|-------------------|
| Agent assembly | `services/support_service.py` | `AgentBuilder`, `AgentProtocol`, `with_strategy("react")` |
| Tool registration | `tools.py` | `@tool(description=...)`, `Registry[str, Any]` |
| Scenario scripts | `repository/scenarios.py` | `Scenario` dataclass, `Registry[str, Scenario]` |
| Scripted LLM | `repository/scripted_llm.py` | `LLMClientProtocol` stand-in, FIFO queue |
| DI wiring | `di/provider.py` | `Provider`, `register()` / `boot()` lifecycle |
| Module wiring | `app.py` | `AgentsModule.configure(...)`, `WebModule.configure(...)` |

## Scenarios

Each scenario is a list of pre-written ReAct completions that the scripted
LLM pops from a FIFO queue:

| Scenario | What happens |
|----------|-------------|
| `happy` | Single tool call — looks up order A-100, returns tracking info |
| `multi_tool` | Two tool calls — looks up order A-102, computes half refund |
| `failure` | Wrong tool name — agent degrades gracefully, answers directly |

## Run it

From this demo's root (so `application.yaml` is discovered):

```bash
cd examples/support-agent
PYTHONPATH=src uv run python -m support_agent
```

Open http://127.0.0.1:8082, pick a scenario, type a question, and watch
the agent reason step-by-step. Override the port without touching yaml:
`QK_WEB__SERVER__PORT=9000`.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/tools` | List registered tools for the console sidebar |
| POST | `/api/ask` | Run one scenario-scripted ReAct turn |

## Layout — read it in this order

Start at the composition root and follow the wiring outward.
Each file has teaching comments explaining the Quadkit convention it follows.

| # | File | Lesson |
|---|------|--------|
| 1 | `src/support_agent/app.py` | ⭐ Composition root: modules → providers |
| 2 | `src/support_agent/main.py` | Lifecycle: `Application.start/stop`, graceful shutdown |
| 3 | `src/support_agent/di/provider.py` | `register()` (bind) vs `boot()` (initialize); DI patterns |
| 4 | `src/support_agent/services/support_service.py` | Agent builder + facade; `Result` error handling |
| 5 | `src/support_agent/controllers/api.py` | Result-returning handlers → auto HTTP status mapping |
| 6 | `src/support_agent/tools.py` | `@tool` decorator; plain async functions as agent tools |
| 7 | `src/support_agent/repository/scenarios.py` | Scripted completions; `Registry` pattern |
| 8 | `src/support_agent/repository/scripted_llm.py` | `LLMClientProtocol` stand-in; FIFO queue |
| 9 | `src/support_agent/ui/pages.py` | Page controllers: serve HTML/assets only, no logic |

```
examples/support-agent/
├── src/support_agent/
│   ├── app.py                 # ⭐ composition root (start here)
│   ├── main.py                # entry point / lifecycle
│   ├── __main__.py            # python -m support_agent
│   ├── di/
│   │   └── provider.py        # DI wiring + boot() assembly
│   ├── services/
│   │   └── support_service.py # AgentBuilder + SupportAgent facade
│   ├── controllers/
│   │   └── api.py             # JSON API: tools + ask
│   ├── repository/
│   │   ├── scenarios.py       # Scripted ReAct completions
│   │   ├── scripted_llm.py    # LLMClientProtocol stand-in
│   │   └── fixtures.py        # Orders + KB data
│   ├── tools.py               # @tool functions: lookup, refund, search
│   └── ui/                    # pages controller + views/ + static/
├── application.yaml           # web section (QK_* overrides win)
└── tests/                     # e2e + unit tests
```

## Tests

```bash
uv run pytest examples/support-agent/tests -q
```

Covers: tool registration, tool behavior, scenario registry, agent facade,
end-to-end API calls (happy, multi-tool, failure, unknown scenario, blank
question, byte-stability), and page/static serving.

## Provider health evidence (local checkout, 2026-11-01)

The example provider reports its local facade as UNHEALTHY before boot and after
shutdown, and HEALTHY once assembled by the real composition root. It uses its
typed configuration for the service label; it does not probe external services or
certify whole-application readiness. The provider drops its facade reference on
shutdown; framework modules own their collaborators. Tests cover these states in
`tests/test_provider_health.py`.

This is a handwritten framework example, not a generated Playground agent start.
See the [gallery representability audit](../../apps/playground/docs/gallery/representability-audit.md)
for the graph/generator gaps and evidence boundaries.

### Explicit ReAct iteration bound

`build_support_agent()` passes `max_iterations=5` to the strategy itself.
`AgentConfig.max_iterations` on the module is not forwarded into an explicitly
built ReAct strategy. A real-executor test drives six non-final scripted steps
and verifies only five tool calls, with one script entry remaining. The returned
response is `Ok` with `metadata.max_iterations_reached=true`; this is a limit
marker, **not** a completed-answer or successful-business-operation guarantee.
