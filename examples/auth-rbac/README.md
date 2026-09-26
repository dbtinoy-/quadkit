# RBAC Console Demo

> Module name: `rbac_console` — run with `PYTHONPATH=examples/auth-rbac/src uv run python -m rbac_console`

Demonstrates **role-based access control** from quadkit-auth through a
browser: pick a seeded persona, watch the live permission matrix flip, try
`authorize()` verdicts for any action/resource pair, and hit guarded article
endpoints that deny or allow based on permission patterns and role
inheritance.

Fully offline against in-memory stores. No build step — vanilla JS + fetch.

## Quadkit concepts used

| Concept | Where in this demo | Your app |
|---------|-------------------|----------|
| Composition root | `app.py` | Replace controllers/providers list |
| Module pattern | `AuthModule`, `WebModule` | Add your own modules |
| Provider lifecycle | `di/provider.py` | Replace with your registrations |
| Result<T,E> pattern | `controllers/api.py` | Return Result from handlers |
| Protocol binding | `repository/session_repository.py` | Swap impl for Postgres/etc |
| Constructor injection | Everywhere | Declare deps as typed params |
| Domain models | `domain/` | Plain dataclasses, no framework imports |
| Boot-time seeding | `data/seed.py` | Your own data initialization |

## What it shows

| Piece | Where | Quadkit API used |
|-------|-------|-------------------|
| Role definitions (patterns + inheritance) | `application.yaml` | `AuthConfig.roles` → auto-consumed by `AuthorizationProvider` |
| Live permission matrix | `controllers/api.py` | `authorize(user, action, resource) -> Result[bool]` per persona |
| Persona login | `controllers/api.py` | `SessionCookieBackend.login/logout`, three seeded users |
| Guarded resources | `controllers/api.py` | deny-before-mutate guard returning 403 with the missing pattern |
| Effective permissions | `controllers/api.py` | `get_role_permissions(role)` expansion incl. inheritance |

## Permission grammar

Roles are defined in `application.yaml` under `auth.roles`:

```yaml
auth:
  roles:
    viewer:
      permissions: [articles.view]
    editor:
      permissions: [articles.*]
      inherits: [viewer]
    admin:
      permissions: ["*"]
      inherits: [editor]
```

Patterns are `resource.action` with bidirectional `*` wildcards.
`AuthorizationProvider` auto-consumes these at boot — no hand-seeding.

Matrix checks: `articles.view/create/update/delete` plus
`admin_console.open` (admin-only).

## Run it

From this demo's root (so `application.yaml` is discovered):

```bash
cd examples/auth-rbac
PYTHONPATH=src uv run python -m rbac_console
```

Open http://127.0.0.1:8090, log in as any persona (password
`Demo-Password-1`). The matrix recomputes live; the try-form runs one
verdict; the articles card shows the create-guard denying viewers.
Override the port without touching yaml: `QK_WEB__SERVER__PORT=9000`.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/login` | Log in as one of the seeded personas |
| POST | `/api/logout` | Invalidate the session cookie |
| GET | `/api/me` | Return the session user's roles and effective permissions |
| GET | `/api/matrix` | The permission grid computed live via authorize() per persona |
| POST | `/api/try` | Run one authorize() verdict for a persona/action/resource triple |
| GET | `/api/articles` | List all articles (requires authentication) |
| POST | `/api/articles` | Create an article (requires articles.create permission) |

## Layout — read it in this order

Start at the composition root and follow the wiring outward.
Each file has teaching comments explaining the Quadkit convention it follows.

| # | File | Lesson |
|---|------|--------|
| 1 | `src/rbac_console/app.py` | ⭐ Composition root: config → modules → providers |
| 2 | `src/rbac_console/main.py` | Lifecycle: `Application.start/stop`, graceful shutdown |
| 3 | `src/rbac_console/di/provider.py` | `register()` (bind) vs `boot()` (initialize); DI patterns |
| 4 | `src/rbac_console/data/seed.py` | Boot-time seeding; `Result` error handling |
| 5 | `src/rbac_console/controllers/api.py` | Result-returning handlers → auto HTTP status mapping |
| 6 | `src/rbac_console/repository/session_repository.py` | Protocol binding (contracts ↔ implementation) |
| 7 | `src/rbac_console/domain/articles.py` · `personas.py` | Framework-agnostic domain stores as singletons |
| 8 | `src/rbac_console/ui/pages.py` | Page controllers: serve HTML/assets only, no logic |

```
examples/auth-rbac/
├── src/rbac_console/
│   ├── app.py                 # ⭐ composition root (start here)
│   ├── main.py                # entry point / lifecycle
│   ├── di/
│   │   └── provider.py        # DI wiring + boot() seeding
│   ├── data/
│   │   └── seed.py            # boot-time data seeding
│   ├── domain/
│   │   ├── articles.py        # ArticleStore (guarded resource)
│   │   └── personas.py        # PersonaDirectory (catalog)
│   ├── controllers/api.py     # JSON API: login/me/matrix/try/articles
│   ├── repository/session_repository.py  # SessionRepositoryProtocol impl
│   └── ui/                    # pages controller + views/ + static/
├── application.yaml           # web/auth sections (QK_* overrides win)
└── tests/                     # e2e flow via ASGITransport
```

## Tests

```bash
uv run pytest examples/auth-rbac/tests -q
```

Covers: persona logins, matrix cells vs direct authorize() calls,
inheritance resolution, admin bypass, try-verdicts matching the matrix, and
the create-guard denying viewers while allowing editors.
