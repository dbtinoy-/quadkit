# quadkit-ai-agents

Agent system for Quadkit Framework - AI agents with tools, strategies, and execution

---

## Overview

Agent orchestration package for the Quadkit Framework. Provides agent base classes, tool registration, execution strategies (ReAct, Plan-and-Execute, Reflexion, Supervisor), observability, and multi-agent coordination — all wired through DI via `AgentsModule`. Zero-config usage starts with sensible defaults.


> Full documentation: [docs.quadkit.dev](https://docs.quadkit.dev)
## Install

```bash
uv add quadkit-ai-agents
```

## Quick Start

```python
from quadkit import Application
from quadkit.di.module import Module, module

from quadkit.ai.agents import AgentsModule
from quadkit.ai.agents.config import AgentConfig
from quadkit.ai.llm import LLMModule


@module(
    imports=[
        LLMModule.stub(),  # provides LLMClientProtocol
        AgentsModule.configure(AgentConfig(max_iterations=10)),
    ]
)
class AppModule(Module):
    pass


async with Application.boot(modules=[AppModule]) as app:
    # use app.container to resolve services
    ...
```

> **Note:** `AgentsModule` requires an LLM client (`LLMClientProtocol`) in the container — provided by `LLMModule` (from `quadkit-ai-llm`). When using a real LLM provider, set `OPENAI_API_KEY` (or configure your provider in `ClientConfig`).

## Configuration

> **Zero-config usage:** Call `AgentsModule.configure()` with no arguments to use defaults.

### Option 1 — YAML file

```yaml
# application.yaml
ai_agents:
  max_iterations: 10
  default_temperature: 0.7
  default_max_tokens: 2048
  enable_tracing: true
```

### Option 2 — Profiles + Environment Variables *(recommended)*

```bash
export QK_AI_AGENTS__MAX_ITERATIONS=15
# Environment variables for each field
```

### Option 3 — Python

```python
from quadkit.ai.agents.config import AgentConfig
from quadkit.ai.agents import AgentsModule

config = AgentConfig(max_iterations=10)
AgentsModule.configure(config)
```

### Config reference

| Field | Default | Env var | Description |
|-------|---------|---------|-------------|
| `enabled` | `True` | `QK_AI_AGENTS__ENABLED` | Enable the agent subsystem |
| `max_iterations` | `10` | `QK_AI_AGENTS__MAX_ITERATIONS` | Maximum reasoning iterations per execution |
| `default_temperature` | `0.7` | `QK_AI_AGENTS__DEFAULT_TEMPERATURE` | Default LLM temperature |
| `default_max_tokens` | `2048` | `QK_AI_AGENTS__DEFAULT_MAX_TOKENS` | Default max tokens for LLM responses |
| `tool_max_retries` | `3` | `QK_AI_AGENTS__TOOL_MAX_RETRIES` | Retry attempts for transient tool errors |
| `enable_tracing` | `True` | `QK_AI_AGENTS__ENABLE_TRACING` | Enable OpenTelemetry tracing |
| `enable_metrics` | `True` | `QK_AI_AGENTS__ENABLE_METRICS` | Enable Prometheus metrics |

## Module Factory Methods

| Method | Description |
|--------|-------------|
| `AgentsModule.configure(config, enable_multi_agent)` | Configure with explicit config |
| `AgentsModule.stub()` | Minimal config for testing |

## Key Features

- **Agent base classes**: `AgentBase` for defining agents with tools and system prompts
- **Execution strategies**: ReAct, Plan-and-Execute, Reflexion, Supervisor
- **Tool system**: `@tool` decorator for registering standalone tool functions
- **Multi-agent coordination**: `AgentAsToolAdapter` for agent-to-agent delegation
- **Observability**: Built-in tracing and metrics via `AgentTracer` and `AgentMetrics`

## Testing

```python
from quadkit.ai.llm import LLMModule

async with Application.boot(modules=[LLMModule.stub(), AgentsModule.stub()]) as app:
    # your test code
    ...
```

> `AgentsModule.stub()` alone fails container validation without an `LLMClientProtocol` in the container — pair it with `LLMModule.stub()` as shown.

## Key Source Files

| File | What it contains |
|------|-----------------|
| `src/quadkit/ai/agents/module.py` | `AgentsModule.configure()` and `stub()` |
| `src/quadkit/ai/agents/config.py` | `AgentConfig` and environment variable bindings |
| `src/quadkit/ai/agents/agent/base.py` | `AgentBase` class with tools and prompts |
| `src/quadkit/ai/agents/executor/executor.py` | `AgentExecutorImpl` — strategy execution loop |
| `src/quadkit/ai/agents/tools/registry.py` | `ToolRegistryImpl` and `@tool` decorator |
| `src/quadkit/ai/agents/strategies/react.py` | ReAct reasoning loop |
| `src/quadkit/ai/agents/di/provider.py` | `AgentsProvider` — registers agents into DI |
