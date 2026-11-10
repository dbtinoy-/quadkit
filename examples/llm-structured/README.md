# LLM Structured Output Demo

A focused, runnable example of **`quadkit-ai-llm`**. Incoming support notes
are extracted into a validated `TicketBrief` `DomainModel` via
`complete_with_schema`, cached in `LLMCache`, and cost-attributed through
`PricingCostEstimator` + `ModelPricing` — with a deterministic local
`LLMClientProtocol` adapter so the demo runs offline with zero API keys.

## What you'll learn

1. `LLMModule` & `LLMClientProtocol` — wire an LLM client behind a swappable
   contract so services never couple to a vendor SDK
2. `complete_with_schema` — generate schema instructions and validate model JSON
   into a typed `DomainModel`
3. `LLMCache` — serve repeated prompts from cache with hit/miss counters
4. `PricingCostEstimator` + `ModelPricing` — compute USD token cost per call
5. `Result` → RFC-9457 `ProblemDetail` — blank prompts return a `422` problem
   response

## Read in order

| # | File | What you learn |
|---|------|----------------|
| 1 | `src/llm_side/app.py` | `LLMModule` + `WebModule` composition root |
| 2 | `src/llm_side/domains/tickets.py` | `TicketBrief` `DomainModel` target schema |
| 3 | `src/llm_side/services/extractor.py` | `complete_with_schema` + `LLMCache` + `PricingCostEstimator` |
| 4 | `src/llm_side/controllers/api.py` | Thin HTTP adapter (`POST /extract`, `GET /stats`) |
| 5 | `tests/` | Real ASGI round trips proving extraction, caching, and cost tracking |

## Run it

```bash
PYTHONPATH=examples/llm-structured/src uv run python -m llm_side   # :8134
```

- `POST /extract` — extract `{"text": "URGENT: Checkout payment capture failing"}` into a validated `TicketBrief`
- `GET /stats` — inspect `LLMCache` hits/misses and cumulative USD cost

## Tests

```bash
uv run pytest examples/llm-structured/tests
```
