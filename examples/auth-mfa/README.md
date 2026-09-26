# MFA Console Demo

> Module name: `mfa_console` — run with `PYTHONPATH=examples/auth-mfa/src uv run python -m mfa_console`

Demonstrates **multi-factor authentication** from quadkit-auth through a
real browser flow: password login issues a *pending* challenge for
MFA-enabled users, a 6-digit TOTP code (or single-use backup code) upgrades
it to a full session, and enrollment/disable live on the profile page.

Fully offline: the seeded `mfa@mfa.demo` account is enrolled at boot, and
tests compute RFC 6238 codes directly from the framework's
`generate_totp_code`.

## Quadkit concepts used

| Concept | Where in this demo | Your app |
|---------|-------------------|----------|
| Composition root | `app.py` | Replace controllers/providers list |
| Module pattern | `AuthModule`, `WebModule` | Add your own modules |
| Provider lifecycle | `di/provider.py` | Replace with your registrations |
| Result<T,E> pattern | `controllers/api.py` | Return Result from handlers |
| Protocol binding | `repository/session_repository.py` | Swap impl for Postgres/etc |
| Constructor injection | Everywhere | Declare deps as typed params |
| Domain models | `repository/` | Plain dataclasses, no framework imports |
| Boot-time seeding | `di/provider.py` boot() | Your own data initialization |

## What it shows

| Piece | Where | Quadkit API used |
|-------|-------|-------------------|
| Pending challenge flow | `controllers/api.py` | pre-auth session row + `MFAManager.verify_totp(user_id, code)` |
| Enrollment (secret + provisioning URI + backup codes) | `controllers/api.py` | `MFAManager.enable_totp(user_id, issuer)` — codes shown once |
| Disable with password re-check | `controllers/api.py` | `authenticate_user` re-verification + `disable_totp` |
| Attempt capping | `controllers/api.py` | 3 wrong codes revoke the pending session back to `/login` |
| Cookie sessions | `repository/session_repository.py`, `di/provider.py` | `SessionCookieBackend` + `SessionRepositoryProtocol` adapter |

## Run it

From this demo's root (so `application.yaml` is discovered):

```bash
cd examples/auth-mfa
PYTHONPATH=src uv run python -m mfa_console
```

Open http://127.0.0.1:8092.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/login` | Password step; MFA-enabled users get a pending challenge cookie |
| POST | `/api/mfa/challenge` | Verify a TOTP/backup code and upgrade to a full session |
| GET | `/api/me` | Return the session user's identity |
| GET | `/api/mfa/status` | MFA enrollment status and remaining backup codes |
| POST | `/api/mfa/enroll` | Enable TOTP; returns secret + provisioning URI + backup codes once |
| POST | `/api/mfa/disable` | Disable TOTP after re-verifying the password |

- Log in as `mfa@mfa.demo` / `Demo-Password-1` → redirected to `/challenge`.
  The current code is computable from the boot-enrolled secret (tests do
  exactly this); in a browser use your authenticator after enrolling.
- Or log in as `plain@mfa.demo` → straight to `/profile`; enroll TOTP there,
  confirm with a code on next login.

## Layout — read it in this order

Start at the composition root and follow the wiring outward.
Each file has teaching comments explaining the Quadkit convention it follows.

| # | File | Lesson |
|---|------|--------|
| 1 | `src/mfa_console/app.py` | ⭐ Composition root: config → modules → providers |
| 2 | `src/mfa_console/main.py` | Lifecycle: `Application.start/stop`, graceful shutdown |
| 3 | `src/mfa_console/di/provider.py` | `register()` (bind) vs `boot()` (initialize); DI patterns |
| 4 | `src/mfa_console/controllers/api.py` | Result-returning handlers → auto HTTP status mapping |
| 5 | `src/mfa_console/repository/session_repository.py` | Protocol binding (contracts ↔ implementation) |
| 6 | `src/mfa_console/ui/pages.py` | Page controllers: serve HTML/assets only, no logic |

```
examples/auth-mfa/
├── src/mfa_console/
│   ├── app.py                 # ⭐ composition root (start here)
│   ├── main.py                # entry point / lifecycle
│   ├── di/
│   │   └── provider.py        # DI wiring + boot() seeding
│   ├── controllers/
│   │   ├── __init__.py
│   │   └── api.py             # JSON API: login/challenge/me/enroll/disable
│   ├── repository/
│   │   └── session_repository.py  # SessionRepositoryProtocol impl
│   └── ui/                    # pages controller + views/ + static/
├── application.yaml           # web/auth sections (QK_* overrides win)
└── tests/                     # e2e flow via ASGITransport
```

## Tests

```bash
uv run pytest examples/auth-mfa/tests -q
```

Covers: plain-user bypass, pending-challenge issuance, code upgrade to full
session, attempt capping, enroll material shape (`otpauth://totp/` URI +
≥8 backup codes), backup-code single-use semantics, and disable-with-password.
