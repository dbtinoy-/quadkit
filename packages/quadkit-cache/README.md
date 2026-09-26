# quadkit-cache

Multi-backend caching system for Quadkit Framework — Redis, Memcached, and in-memory caching.

---

## Overview

Multi-backend async caching for the Quadkit Framework. Supports Redis, in-memory,
and Memcached backends with stampede protection, circuit breaker, `Result`-aware
caching, and domain model round-trip serialization.

Configure backends via `CacheModule.configure()` and inject `CacheBackendProtocol`
into any service. The `@cacheable` decorator provides cache-aside logic with
automatic key generation and Result support.


> Full documentation: [docs.quadkit.dev](https://docs.quadkit.dev)
## Install

```bash
uv add quadkit-cache
# Optional extras
uv add "quadkit-cache[redis,memcached,semantic]"
```

## Quick Start

```python
from quadkit import Application
from quadkit.di.module import Module, module
from quadkit.cache import CacheModule, CacheConfig
from quadkit.cache.config import CacheBackendConfig
from quadkit.cache.types import BackendType
from quadkit.contracts.infra.cache import CacheBackendProtocol


@module(
    imports=[
        CacheModule.configure(
            CacheConfig(
                backends=[
                    CacheBackendConfig(
                        name="default",
                        type=BackendType.REDIS,
                        default=True,
                        redis_url="redis://localhost:6379/0",
                    )
                ]
            )
        )
    ]
)
class AppModule(Module):
    pass


async def main():
    async with Application.boot(modules=[AppModule]) as app:
        cache = await app.container.resolve(CacheBackendProtocol)
        await cache.set("greeting", "hello", ttl=60)
        value = await cache.get("greeting")
        print(value.unwrap())  # "hello"


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
```

## Configuration

> **Zero-config usage:** Call `CacheModule.configure()` with no arguments; backends are then loaded from the `cache:` section of `application.yaml`. Use `CacheModule.stub()` (in-memory) in tests.

### Option 1 — YAML file

```yaml
# application.yaml
cache:
  enabled: true
  backends:
    - name: redis
      type: redis
      default: true
      redis_url: "redis://localhost:6379/0"
      default_ttl: 300
  service:
    enable_protection: true
```

### Option 2 — Profiles + Environment Variables *(recommended)*

```bash
export QK_CACHE__ENABLED=true
export QK_CACHE__BACKENDS__0__TYPE=redis
export QK_CACHE__BACKENDS__0__REDIS_URL=redis://localhost:6379/0
```

### Option 3 — Python

```python
from quadkit.cache import CacheModule, CacheConfig
from quadkit.cache.config import CacheBackendConfig
from quadkit.cache.types import BackendType

CacheModule.configure(
    CacheConfig(
        backends=[
            CacheBackendConfig(
                name="redis",
                type=BackendType.REDIS,
                default=True,
                redis_url="redis://localhost:6379/0",
            )
        ]
    )
)
```

### Config reference

| Field | Default | Env var | Description |
|-------|---------|---------|-------------|
| `enabled` | `True` | `QK_CACHE__ENABLED` | Enable the cache module |
| `backends[].name` | — | `QK_CACHE__BACKENDS__0__NAME` | Unique backend name |
| `backends[].type` | — | `QK_CACHE__BACKENDS__0__TYPE` | Backend type: `redis`, `memory`, `memcached` |
| `backends[].redis_url` | — | `QK_CACHE__BACKENDS__0__REDIS_URL` | Redis connection URL |
| `backends[].default_ttl` | `null` | `QK_CACHE__BACKENDS__0__DEFAULT_TTL` | Default TTL in seconds |
| `service.enable_protection` | `True` | `QK_CACHE__SERVICE__ENABLE_PROTECTION` | Stampede protection |
| `service.circuit_breaker_enabled` | `False` | `QK_CACHE__SERVICE__CIRCUIT_BREAKER_ENABLED` | Circuit breaker on backend failures |

## Module Factory Methods

| Method | Description |
|--------|-------------|
| `CacheModule.configure(...)` | Configure with explicit CacheConfig |
| `CacheModule.stub()` | In-memory backend for unit testing |

## Key Features

- **Multi-backend** — Redis, in-memory, and Memcached with a unified protocol
- **Stampede protection** — Distributed lock on cold reads prevents thundering herd
- **Circuit breaker** — Opens on repeated backend failures, falls through to origin
- **`@cacheable` decorator** — Cache-aside with automatic key generation and Result support
- **Domain model serialization** — Type-tagged JSON envelope preserves type identity round-trip
- **Production security** — Blocks insecure Redis passwords when QK_ENV=production

## Testing

```python
from quadkit.cache import CacheService

async with Application.boot(modules=[CacheModule.stub()]) as app:
    cache = await app.container.resolve(CacheService)
    await cache.set("key", "value", ttl=60)
    assert await cache.get("key") == "value"
```

## Key Source Files

| File | What it contains |
|------|-----------------|
| `src/quadkit/cache/module.py` | CacheModule with configure() and stub() |
| `src/quadkit/cache/config.py` | CacheConfig, CacheBackendConfig, CacheServiceConfig |
| `src/quadkit/cache/di/provider.py` | CacheProvider boot and registration |
| `src/quadkit/cache/decorators.py` | @cacheable decorator |
| `src/quadkit/cache/backends/` | Redis, in-memory, and Memcached implementations |
