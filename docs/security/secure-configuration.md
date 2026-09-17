# Secure configuration

Quadkit's security posture is expressed in configuration; getting it
right is mostly a matter of knowing which defaults are already
conservative and which decisions are yours.

## Secrets never live in YAML

- `application.yaml` is for topology and defaults — it is meant to be
  committed. Secrets (API keys, database URLs with credentials, tokens)
  arrive through the environment: every typed key overrides via
  `QK_<SECTION>__<KEY>`, e.g. `QK_WEB__SERVER__PORT=8080`.
- `quadkit[security]` adds `cryptography`-backed helpers and
  `quadkit-web[security]` adds `itsdangerous` for signed tokens — both
  optional extras, installed deliberately.

See [configuration](../getting-started/configuration.md) for the
override mechanics.

## The web surface, by default and by choice

| Knob (under `web.*`) | Default | Hardening guidance |
| --- | --- | --- |
| `security.enable_csrf` | **on** | Keep for browser-facing apps; the token travels in the `csrf_token` cookie + `X-CSRF-Token` header. Disable explicitly (`false`) only for non-browser JSON APIs. |
| `security.allowed_hosts` | unset | Pin the hosts you serve in production. |
| `security.custom_headers` | unset | Add your org's required security headers here. |
| `debug_routes` (+ `debug_routes_token`, environment gate) | opt-in | Debug endpoints only serve when explicitly enabled and gated; leave off in production. |
| `api_docs` (`/docs`, `/redoc`, `/openapi.json`) | on | Served by default; restrict or disable for private APIs that should not advertise their schema. |

## CSRF in practice

The default-on CSRF middleware is why a bare `curl -X POST` against a
fresh app answers `403 csrf_error: missing token`. That is the system
working. Two correct postures:

1. **Browser-facing app** — keep it on; pages obtain the token from the
   cookie and echo it in the header.
2. **Server-to-server JSON API** — disable it explicitly
   (`web.security.enable_csrf: false`) and say why in a comment; the
   shipped guide examples do exactly this. Choose an authentication
   story for those routes instead.

## Error responses do not leak

Unexpected exceptions answer `500` with a minimal body
(`{"success": false, "error": {"type": "internal_server_error", ...}}`) —
stack traces and internals never reach the client. Validation and
domain failures render as problem responses with client-safe detail
(see [error handling](../guides/error-handling.md)).

## Supply chain

- **Pin the 0.x line.** Exact pins (`quadkit-web==0.0.3`) or tight
  ranges (`>=0.0.3,<0.1.0`) until `1.0`; review release notes on each
  upgrade. See [stability](../reference/stability.md).
- The five public distributions are the whole public surface; optional
  extras pull only generic ecosystem dependencies (Starlette, pydantic,
  Granian/Uvicorn/Hypercorn, pytest, ...).

If you find a gap in any of the above, report it privately — see
[vulnerability reporting](./vulnerability-reporting.md).
