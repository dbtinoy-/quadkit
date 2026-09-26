# API Keys Console Demo

Demonstrates **machine authentication** from quadkit-auth: manage API keys
in a browser (issue with scopes, list, revoke), then call a protected JSON
endpoint with the `X-API-Key` header. Raw keys are shown exactly once; only
hashes persist. Fully offline.

## Quadkit concepts used

| Concept | File | Your app |
|---------|------|----------|
| Composition root | `app.py` | Your `app.py` — modules + providers |
| Auto-config | `application.yaml` | All config lives here, not in code |
| Provider lifecycle | `di/provider.py` | Your app's DI wiring |
| Dual binding (concrete + protocol) | `di/provider.py` | Framework resolves contracts |
| Result-based controllers | `controllers/api.py` | HTTP → Result → ProblemDetail |
| Repository pattern | `repository/keys_repository.py` | Your persistence adapters |
| Cookie vs. X-API-Key auth | `controllers/api.py` | Browser + machine access |
| Boot-time seeding | `domain/seed.py` | Database migrations, fixtures |

## Layout — read it in this order

Start at the composition root and follow the wiring outward.
Each file has teaching comments explaining the Quadkit convention it follows.

| # | File | Lesson |
|---|------|--------|
| 1 | `src/apikey_console/app.py` | ⭐ Composition root: config → modules → providers |
| 2 | `src/apikey_console/main.py` | Lifecycle: `Application.start/stop`, graceful shutdown |
| 3 | `src/apikey_console/di/provider.py` | `register()` (bind) vs `boot()` (initialize); dual binding |
| 4 | `src/apikey_console/domain/` | Boot-time seeding; framework-agnostic seed service |
| 5 | `src/apikey_console/repository/` | Protocol binding: in-memory implementations of contracts |
| 6 | `src/apikey_console/controllers/api.py` | Result-returning handlers → auto HTTP status mapping |
| 7 | `src/apikey_console/controllers/pages.py` | Page controllers: serve HTML/assets only, no logic |

```
examples/auth-apikeys/
├── application.yaml          # web + auth config (auto-discovered)
├── src/apikey_console/
│   ├── app.py                # composition root (start here)
│   ├── main.py               # entry point / lifecycle
│   ├── di/provider.py        # DI wiring + boot() assembly
│   ├── domain/               # framework-agnostic seed service
│   ├── repository/           # in-memory protocol implementations
│   ├── controllers/api.py    # JSON API: login, keys CRUD, /api/me
│   ├── controllers/pages.py  # static file-serving routes
│   └── ui/                   # views/*.html + static/
└── tests/                    # end-to-end issue/auth/revoke flows
```

## Run it

```bash
cd examples/auth-apikeys
PYTHONPATH=src uv run python -m apikey_console
# → http://127.0.0.1:8091
```

Log in as `admin@keys.demo` / `Demo-Password-1`. Create a key with scopes,
then call the machine endpoint:

```bash
curl -H "X-API-Key: <raw-key>" http://127.0.0.1:8091/api/me
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/login` | Authenticate with email/password and set session cookie |
| POST | `/api/logout` | Invalidate the session cookie |
| GET | `/api/keys` | List API keys for the authenticated user |
| POST | `/api/keys/create` | Issue a new API key (raw secret shown once) |
| POST | `/api/keys/{key_id}/revoke` | Revoke an API key |
| GET | `/api/me` | Machine authentication via `X-API-Key` header |

## Tests

```bash
cd examples/auth-apikeys
uv run pytest tests -q
```

Covers: raw key shown exactly once, valid-key machine identity, missing/
garbage/revoked keys all 401, anonymous management blocked (401), and key
listing scoped to the session user.
