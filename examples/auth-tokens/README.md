# Auth Tokens

Token login with HMAC-signed bearer tokens (Python stdlib only),
protected routes, and dependency-injected auth — the canonical starter
for the Result/ProblemDetail bridge: expected failures are `Err(...)`
values rendered as RFC-9457 bodies, not raised `HTTPError`s.

**Demonstrates:** a DI-bound `TokenService`, 401 handling via
`Err(AuthenticationError)` → ProblemDetail, request injection
(`request: Request`), `SecretStr` config knobs, and httpx-ASGI round
trips over the real composition root.

> The signing scheme is deliberately tiny so the flow fits one read. For
> production, swap `TokenService.verify` for your JWT/OIDC validation —
> the controller and tests stay unchanged.

Demo credentials: `ada / wonderland` (admin), `grace / compiler` (reader).

## Layout

```
src/auth_tokens/
├── app.py             # composition root
├── main.py            # serve() with try/finally app.stop()
├── config.py          # AuthTokensConfig (token_secret, token_ttl)
├── controllers/api.py # SessionController — POST /session, GET /me
├── services/tokens.py # TokenService (issue/verify → Result)
└── di/provider.py     # binds service + controller
```

## Run

```bash
pip install quadkit[web]
PYTHONPATH=src python -m auth_tokens
curl -X POST localhost:8122/session -H 'content-type: application/json' \
  -d '{"username": "ada", "password": "wonderland"}'
curl localhost:8122/me -H "Authorization: Bearer <token>"
```

The signing secret is `auth_tokens.token_secret`
(`QK_AUTH_TOKENS__TOKEN_SECRET` in production).

## Test

```bash
PYTHONPATH=src pytest tests/
```
