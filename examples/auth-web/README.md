# Auth Web Demo

Demonstrates the **authentication subsystem** of Quadkit through a real
browser flow: register → login → cookie session → protected profile with JWT
claims and session management → change password → logout.

Server-rendered pages are plain HTML + vanilla JS calling a JSON API — no
build step. Everything runs offline against in-memory stores.

## What it shows

| Piece | Where | Quadkit API used |
|-------|-------|-------------------|
| Registration (policy-checked) | `src/auth_web/controllers/api.py` | `AuthenticationService.register_user(RegisterRequest)` |
| Login with lockout | `controllers/api.py` | `authenticate_user(email, password)` — constant-time verify, `AccountLockedError` after 5 failures |
| JWT issue + verify | `controllers/api.py` | `create_token(user) -> AuthToken`, `verify_token(token) -> Result[VerifiedToken]` |
| Cookie sessions | `repository/session_repository.py`, `di/provider.py` | `SessionCookieBackend.login/authenticate/logout`, `SessionRepositoryProtocol` adapter |
| RBAC claims | `controllers/api.py` | role definitions seeded via `AuthorizationService.set_roles`, effective permissions via `get_role_permissions` |
| Change password | `services/password_change.py` | composed Argon2id/bcrypt hasher + `PasswordPolicyProtocol` |
| UI assets | `ui/` | vanilla JS `fetch` client (`app.js`), HTML views, stylesheet |

## Run it

```bash
PYTHONPATH=examples/auth-web/src uv run python -m auth_web
```

Open http://127.0.0.1:8081 and log in with the seeded account (defined in
`application.yaml`):

```
email:    admin@auth.demo
password: Admin-Pass-123!
```

Walk the flows: register a second account, view the profile's token claims
(roles/permissions/key_id/expiry), revoke sessions from another browser,
change your password and re-login.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/register` | Create an account and start a session |
| POST | `/api/login` | Verify credentials and set the session cookie |
| POST | `/api/logout` | Invalidate the session cookie |
| GET | `/api/me` | Return the session's identity, or 401 when anonymous |
| GET | `/api/profile` | Identity + fresh JWT claims + active sessions for this user |
| POST | `/api/profile/password` | Change the session user's password (requires current password) |
| POST | `/api/sessions/{session_id}/revoke` | Revoke one of the session user's active sessions |
| POST | `/api/forgot-password` | Request a password reset token for the given email |
| POST | `/api/reset-password` | Reset a password using a valid reset token |
| POST | `/api/verify-email` | Verify the session user's email with a verification token |
| POST | `/api/send-verification` | Send a verification email for the session user |

## Quadkit Concepts

| Concept | Where in this demo | Your app |
|---------|-------------------|----------|
| Composition root | `app.py` | Replace controllers/providers list |
| Module pattern | `AuthModule`, `WebModule` | Add your own modules |
| Provider lifecycle | `di/provider.py` | Replace with your registrations |
| Result<T,E> pattern | `controllers/api.py` | Return Result from handlers |
| Protocol binding | `repository/session_repository.py` | Swap impl for Postgres/etc |
| Constructor injection | Everywhere | Declare deps as typed params |
| Domain models | `services/` | Plain dataclasses, no framework imports |
| Boot-time seeding | `services/seed.py` | Your own data initialization |

## Notes

- Every command boots a fresh in-memory world: users and sessions reset per
  process.
- The demo seeds users from `application.yaml` at boot; registration adds more.
- Host/port come from `application.yaml` (`web.server`); override via
  `QK_WEB__SERVER__PORT` without editing the file.

## Layout — read it in this order

Start at the composition root and follow the wiring outward.
Each file has teaching comments explaining the Quadkit convention it follows.

| # | File | Lesson |
|---|------|--------|
| 1 | `src/auth_web/app.py` | ⭐ Composition root: config → modules → providers |
| 2 | `src/auth_web/main.py` | Lifecycle: uvicorn boot, graceful shutdown |
| 3 | `src/auth_web/di/provider.py` | Provider wiring: seeds users + roles, wires cookie backend |
| 4 | `src/auth_web/services/seed.py` | Boot-time seeding from `AuthConfig` in YAML |
| 5 | `src/auth_web/services/password_change.py` | Composed service: Argon2id/bcrypt hasher + policy protocol |
| 6 | `src/auth_web/repository/` | Protocol binding: `InMemorySessionRepository` adapter |
| 7 | `src/auth_web/controllers/api.py` | Result-returning handlers → auto HTTP status mapping |
| 8 | `src/auth_web/ui/` | Page controllers: serve HTML/assets only, no logic |

```
examples/auth-web/
├── src/auth_web/
│   ├── controllers/          # JSON API (register/login/logout/me/profile/password/sessions)
│   │   └── api.py
│   ├── di/provider.py        # AuthWebProvider (seeds user + roles, wires cookie backend)
│   ├── repository/           # InMemorySessionRepository (SessionRepositoryProtocol adapter)
│   ├── services/
│   │   ├── password_change.py  # PasswordChangeService (composed-hasher aware)
│   │   └── seed.py            # DemoSeedService (reads AuthConfig.users from yaml)
│   ├── ui/                   # views/*.html + static/app.js, style.css
│   ├── app.py                # Composition root (build_modules, build_providers, create_app)
│   └── main.py               # ASGI boot (run_server)
├── application.yaml          # Runtime config (web + auth sections)
└── tests/                    # end-to-end API flow tests (httpx ASGI transport)
```

## Tests

```bash
uv run pytest examples/auth-web/tests -q
```

The suite drives the real ASGI app through an httpx transport: full register/
login/profile/password/logout journeys including lockout, duplicate email,
wrong-current-password, session revocation across browsers, and RBAC claim
expansion.
