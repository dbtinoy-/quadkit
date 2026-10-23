# quadkit-auth

Authentication and authorization for the Quadkit Framework — JWT, OAuth2, SAML, RBAC, and multi-tenancy.

---

## Overview

Complete authentication and authorization stack for Quadkit — JWT, OAuth2, RBAC,
SAML, passkeys, and MFA. Provides a production-ready auth layer with multiple
authentication strategies, policy-based access control, session management, and
seamless integration with `quadkit-web` middleware.

Use `AuthModule.configure()` to register the auth bundle and protect routes with
`@require_auth`, `@require_roles`, and `@require_permissions` decorators.


> Full documentation: [oridecon.dev/quadkit](https://oridecon.dev/quadkit)
## Install

```bash
uv add quadkit-auth
# Optional extras
uv add "quadkit-auth[oauth2,saml]"
```

## Quick Start

```python
from quadkit import Application
from quadkit.di.module import Module, module
from quadkit.auth import AuthModule, AuthConfig, JWTConfig


@module(
    imports=[
        AuthModule.configure(
            config=AuthConfig(
                secret_key="your-secret-key",
                token=JWTConfig(secret_key="your-jwt-secret"),
            )
        )
    ]
)
class AppModule(Module):
    pass


async def main() -> None:
    async with Application.boot(modules=[AppModule]) as app:
        # app is running — resolve services from app.container
        ...


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
```

## Configuration

> **Note:** `AuthConfig` requires both `secret_key` and `token.secret_key` — pass an explicit config via `AuthModule.configure()`.

### Option 1 — YAML file

```yaml
# application.yaml
auth:
  secret_key: "your-secret-key"
  token:
    secret_key: "your-jwt-secret"
    algorithm: "HS256"
    access_token_expire: "30m"
  rbac:
    enabled: true
    default_role: "viewer"
```

### Option 2 — Profiles + Environment Variables *(recommended)*

```bash
export QK_AUTH__SECRET_KEY=your-secret-key
export QK_AUTH__TOKEN__SECRET_KEY=your-jwt-secret
export QK_AUTH__TOKEN__ALGORITHM=HS256
export QK_AUTH__RBAC__DEFAULT_ROLE=viewer
```

### Option 3 — Python

```python
from quadkit.auth import AuthModule, AuthConfig, JWTConfig
from quadkit.contracts.core import Duration

config = AuthConfig(
    secret_key="your-secret-key",
    token=JWTConfig(
        secret_key="your-jwt-secret",
        algorithm="HS256",
        access_token_expire=Duration.minutes(30),
    ),
)
AuthModule.configure(config)
```

### Config reference

| Field | Default | Env var | Description |
|-------|---------|---------|-------------|
| `secret_key` | — | `QK_AUTH__SECRET_KEY` | Top-level signing secret (**required**) |
| `token.secret_key` | — | `QK_AUTH__TOKEN__SECRET_KEY` | JWT signing secret (**required**) |
| `token.algorithm` | `HS256` | `QK_AUTH__TOKEN__ALGORITHM` | JWT algorithm: HS256, RS256, ES256 |
| `token.access_token_expire` | `30m` | `QK_AUTH__TOKEN__ACCESS_TOKEN_EXPIRE` | Access token lifetime (duration string, e.g. `30m`, `1h30m`) |
| `rbac.enabled` | `True` | `QK_AUTH__RBAC__ENABLED` | Enable RBAC |
| `rbac.default_role` | `viewer` | `QK_AUTH__RBAC__DEFAULT_ROLE` | Default role for new users |

## Module Factory Methods

| Method | Description |
|--------|-------------|
| `AuthModule.configure(...)` | Configure with explicit AuthConfig |
| `AuthModule.stub()` | Minimal config for testing |

## Key Features

- **JWT authentication** — HS256/RS256, key rotation, token blacklisting
- **OAuth2 / OIDC** — authlib-backed: Google, GitHub, custom providers
- **SAML 2.0** — Enterprise SSO via pysaml2
- **Passkeys (WebAuthn)** — FIDO2 device-based authentication
- **MFA (TOTP)** — Time-based one-time passwords
- **RBAC** — Role/permission inheritance with policy expressions
- **Session management** — Device-aware sessions with concurrency limits
- **Token binding** — IP address binding to prevent token theft

## Testing

```python
async with Application.boot(modules=[AuthModule.stub()]) as app:
    # your test code
    ...
```

## Key Source Files

| File | What it contains |
|------|-----------------|
| `src/quadkit/auth/module.py` | AuthModule definition |
| `src/quadkit/auth/config.py` | AuthConfig, JWTConfig, RBACConfig |
| `src/quadkit/auth/di/bundle_provider.py` | AuthBundleProvider wiring |
| `src/quadkit/auth/di/sub_providers/token_provider.py` | TokenProvider (boots policy) |
| `src/quadkit/auth/authn/jwt.py` | JWTTokenManager implementation |
| `src/quadkit/auth/authn/_jwt_lifecycle.py` | verify_token (enforces policy) |
| `src/quadkit/auth/authz/service.py` | AuthorizationService |

## JWT verification policy

`quadkit-auth` enforces **verified-only** JWT decoding — signature verification
cannot be disabled.

| Environment | Secret present | Behaviour |
|-------------|---------------|-----------|
| `PRODUCTION` / `STAGING` | yes | Verified-only. Boot succeeds. |
| `PRODUCTION` / `STAGING` | **no** | **Raises `ConfigurationError` at boot.** |
| `DEVELOPMENT` | yes | Verified-only. Boot succeeds. |
| `DEVELOPMENT` | **no** | Verified-only. Boots with a generated **ephemeral secret** (tokens invalidated on restart). |

### Stable development secret

For multi-service development, set a stable secret via environment variable:
```bash
export QK_AUTH__TOKEN__SECRET_KEY="a-stable-dev-secret-at-least-32-chars"
```

Via Python config:
```python
from quadkit.auth.config import AuthConfig, JWTConfig

config = AuthConfig(
    secret_key="a-stable-dev-secret-at-least-32-chars",
    token=JWTConfig(
        secret_key="a-stable-dev-secret-at-least-32-chars",
    ),
)
```

This prevents the common mistake of silently trusting unverified tokens
in production when a secret env-var is missing.
