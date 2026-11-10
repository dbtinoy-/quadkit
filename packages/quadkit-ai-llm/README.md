# quadkit-ai-llm

LLM client layer for the Quadkit Framework — OpenAI, Anthropic, Ollama, Cohere, Groq, Mistral

---

## Overview

LLM client layer for the Quadkit Framework. Provides typed, async-first clients for 15 providers, multi-provider routing, thinking/reasoning control, structured extraction, streaming, embeddings, and model management — all wired through the DI container via `LLMModule`. `configure()` with no arguments uses the defaults but boots the client eagerly, so the provider's API key (e.g. `OPENAI_API_KEY`) must be available; `stub()` is the test-safe path.


> Full documentation: [docs.quadkit.dev](https://docs.quadkit.dev)
## Install

```bash
uv add quadkit-ai-llm
# Optional extras
uv add "quadkit-ai-llm[openai,anthropic,ollama]"
```

## Quick Start

```python
from quadkit import Application
from quadkit.di.module import Module, module

from quadkit.ai.llm import LLMModule
from quadkit.ai.llm.config import ClientConfig


@module(
    imports=[
        LLMModule.configure(
            ClientConfig(provider="anthropic", model="claude-sonnet-4-6")
        )
    ]
)
class AppModule(Module):
    pass


async with Application.boot(modules=[AppModule]) as app:
    # use app.container to resolve services
    ...
```

## Configuration

> **Zero-config usage:** `LLMModule.configure()` with no arguments uses default settings (provider `openai`, model `gpt-4-turbo`), but the client is created eagerly at boot — set the provider's API key via config or the provider SDK env var first. For tests, use `LLMModule.stub()`.

### Option 1 — YAML file

```yaml
# application.yaml
ai_llm:
  provider: "anthropic"
  model: "claude-sonnet-4-6"
  api_key: "${QK_AI_LLM__API_KEY}"
  temperature: 0.7
  max_tokens: null
```

### Option 2 — Profiles + Environment Variables *(recommended)*

```bash
export QK_AI_LLM__PROVIDER=anthropic
# Environment variables for each field
```

### Option 3 — Python

```python
from quadkit.ai.llm.config import ClientConfig
from quadkit.ai.llm import LLMModule

config = ClientConfig(
    provider="anthropic",
    model="claude-sonnet-4-6",
)
LLMModule.configure(config)
```

### Config reference

| Field | Default | Env var | Description |
|-------|---------|---------|-------------|
| `enabled` | `True` | `QK_AI_LLM__ENABLED` | Enable the LLM subsystem |
| `provider` | `openai` | `QK_AI_LLM__PROVIDER` | LLM provider |
| `model` | `gpt-4-turbo` | `QK_AI_LLM__MODEL` | Model name |
| `api_key` | `None` | `QK_AI_LLM__API_KEY` | Provider API key |
| `api_base` | `None` | `QK_AI_LLM__API_BASE` | Custom endpoint (Azure, local, proxy) |
| `temperature` | `0.7` | `QK_AI_LLM__TEMPERATURE` | Sampling temperature (0.0–2.0) |
| `max_tokens` | `None` | `QK_AI_LLM__MAX_TOKENS` | Response token limit |
| `timeout` | `60.0` | `QK_AI_LLM__TIMEOUT` | Request timeout in seconds |
| `enable_cache` | `False` | `QK_AI_LLM__ENABLE_CACHE` | Cache responses |
| `cache_ttl` | `3600` | `QK_AI_LLM__CACHE_TTL` | Cache TTL in seconds |
| `thinking` | `None` | — | Reasoning/thinking control configuration |

## Module Factory Methods

| Method | Description |
|--------|-------------|
| `LLMModule.configure(config)` | Single-provider client |
| `LLMModule.configure(routing=LLMConfig())` | Multi-provider routing cascade |
| `LLMModule.stub()` | No-op client for tests |

## Key Features

- **15 providers**: OpenAI, Anthropic, Google Gemini, Azure OpenAI, AWS Bedrock, Google Vertex AI, Ollama, Groq, Mistral, Cohere, DeepSeek, Fireworks, Together, Cloudflare Workers, OpenRouter
- **Multi-provider routing**: Sequential, cost-optimized, and latency-optimized strategies
- **Thinking/reasoning control**: Extended thinking with token budget and suppression
- **Structured extraction**: JSON schema and Pydantic model extraction
- **Streaming**: Async streaming response support
- **Embeddings**: Text embedding client with same provider
- **Caching**: Response-level caching with configurable TTL

## Testing

```python
async with Application.boot(modules=[LLMModule.stub()]) as app:
    # your test code
    ...
```

## Key Source Files

| File | What it contains |
|------|-----------------|
| `src/quadkit/ai/llm/module.py` | `LLMModule.configure()` and `LLMModule.stub()` |
| `src/quadkit/ai/llm/config.py` | `ClientConfig` |
| `src/quadkit/ai/llm/routing/config.py` | `LLMConfig`, `ProviderConfig` for routing |
| `src/quadkit/ai/llm/di/provider.py` | `LLMProvider` — registers and boots the client |
| `src/quadkit/ai/llm/clients/` | Provider implementations |
| `src/quadkit/ai/llm/thinking/` | `ThinkingConfig` handling and suppression |
| `src/quadkit/ai/llm/exceptions.py` | Full exception hierarchy |
