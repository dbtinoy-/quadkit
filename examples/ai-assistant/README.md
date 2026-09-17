# AI Assistant — external integration

> **Labelled external integration:** Quadkit ships no AI client. This
> starter shows the seam: the controller depends on a small
> `AssistantClient` protocol; the production binding calls any
> OpenAI-compatible `/chat/completions` endpoint over `httpx` (already a
> `quadkit-web` dependency), and tests bind a fake — no network, no API
> key.

**Demonstrates:** protocol-first integration design, typed-config
integration settings (`ai_assistant.gateway_url`, `api_key`, `model`),
`Err(ValidationError)` → 422 ProblemDetail, and constructor-injected
fakes via `create_app(client=...)`.

## Layout

```
src/ai_assistant/
├── app.py             # composition root (client= test seam)
├── main.py            # serve() with try/finally app.stop()
├── config.py          # AIAssistantConfig (gateway_url/api_key/model)
├── controllers/api.py # ChatController — POST /chat
├── services/client.py # AssistantClient protocol + HTTP binding
└── di/provider.py     # builds client from config in boot()
```

## Run

```bash
pip install quadkit[web]
QK_AI_ASSISTANT__GATEWAY_URL=https://api.openai.com/v1 \
QK_AI_ASSISTANT__API_KEY=sk-... \
PYTHONPATH=src python -m ai_assistant
curl -X POST localhost:8126/chat -H 'content-type: application/json' \
  -d '{"message": "hello"}'
```

## Test

```bash
PYTHONPATH=src pytest tests/
```
