# quadkit-sql

SQL database abstractions for Quadkit Framework — Postgres, MySQL, SQLite with migrations, repositories, and query building.

---

## Overview

`quadkit-sql` provides an async SQLAlchemy ORM layer with the repository pattern, unit-of-work, connection pooling, multi-database support, Alembic migrations, and optional HMAC audit checksums. All database operations are wired through `DatabaseProviderProtocol` in the DI container.

---


> Full documentation: [oridecon.dev/quadkit](https://oridecon.dev/quadkit)
## Install

```bash
uv add quadkit quadkit-sql

# With async PostgreSQL driver
uv add "quadkit-sql[postgres]"

# With async MySQL driver
uv add "quadkit-sql[mysql]"

# With SQLite async driver
uv add "quadkit-sql[sqlite]"
```

## Quick Start

```python
from quadkit import Application, StandardModule
from quadkit.di.module import Module, module
from quadkit.sql import DatabaseModule
from quadkit.sql.config import DatabaseConfig


@module(
    imports=[
        DatabaseModule.configure(
            DatabaseConfig(url="postgresql+asyncpg://user:pass@localhost/mydb")
        )
    ]
)
class AppModule(Module):
    pass


async def main() -> None:
    async with Application.boot(modules=[AppModule]) as app:
        from quadkit.contracts.data.sql.database import DatabaseProviderProtocol

        db = await app.container.resolve(DatabaseProviderProtocol)
        result = await db.execute_query("SELECT 1")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
```

## Configuration

> **Zero-config usage:** Call `DatabaseModule.configure()` with no arguments to use all defaults (SQLite).

### Option 1 — YAML file

```yaml
# application.yaml
sql:
  backend:
    url: "${QK_SQL__BACKEND__URL}"
  pool:
    min_size: 2
    max_size: 10
    timeout: 30
  operations:
    echo: false
```

### Option 2 — Profiles + Environment Variables *(recommended)*

```bash
export QK_SQL__BACKEND__URL=postgresql+asyncpg://user:pass@host/db
export QK_SQL__POOL__MAX_SIZE=20
export QK_SQL__POOL__TIMEOUT=60
```

### Option 3 — Python

```python
from quadkit.sql import DatabaseModule
from quadkit.sql.config import DatabaseConfig

DatabaseModule.configure(
    DatabaseConfig(
        url="postgresql+asyncpg://user:pass@localhost/mydb",
    )
)
```

### Config reference

| Field | Default | Env var | Description |
|-------|---------|---------|-------------|
| `backend.url` | `"sqlite:///data.db"` | `QK_SQL__BACKEND__URL` | Database connection URL |
| `pool.min_size` | `1` | `QK_SQL__POOL__MIN_SIZE` | Minimum pool connections |
| `pool.max_size` | `10` | `QK_SQL__POOL__MAX_SIZE` | Maximum pool connections |
| `pool.timeout` | `30` | `QK_SQL__POOL__TIMEOUT` | Pool acquire timeout (seconds) |
| `operations.echo` | `False` | `QK_SQL__OPERATIONS__ECHO` | Echo SQL statements |
| `audit_hmac_key` | `None` | `QK_SQL__AUDIT_HMAC_KEY` | HMAC key for audit checksums |

## Module Factory Methods

| Method | Description |
|--------|-------------|
| `DatabaseModule.configure(config, enable_migrations, migration_dir)` | Configure with explicit `DatabaseConfig` |
| `DatabaseModule.scope(*repositories)` | Scope repository classes into a feature module |
| `DatabaseModule.stub(config=None)` | In-memory SQLite for testing |

## Key Features

- **Repository pattern** — `SQLRepository` base class with find, create, update, delete, count
- **Unit of work** — `AbstractUnitOfWork` tracks changes and publishes domain events on commit
- **Multi-database** — `NamedDatabaseConfig` for multiple backends resolved via `Annotated[DatabaseProviderProtocol, Named("analytics")]`
- **Connection pooling** — SQLAlchemy async pool with configurable min/max size
- **Alembic migrations** — optional, run on boot only when `enable_migrations=True` (off by default)
- **HMAC audit checksums** — optional signing of write operations for integrity verification
- **Production security** — blocks default passwords (`:password@`, `:postgres@`, etc.) when `QK_ENV=production`

## Testing

```python
from quadkit import Application
from quadkit.sql import DatabaseModule
from quadkit.sql.config import DatabaseConfig


async def test_repository():
    async with Application.boot(
        modules=[
            DatabaseModule.stub(DatabaseConfig(url="sqlite+aiosqlite:///:memory:"))
        ]
    ) as app:
        db = await app.container.resolve(DatabaseProviderProtocol)
        # run your test queries
```

## Key Source Files

| File | What it contains |
|------|----------------|
| `src/quadkit/sql/module.py` | `DatabaseModule.configure()`, `.scope()`, `.stub()` |
| `src/quadkit/sql/config.py` | `DatabaseConfig`, `DatabasePoolConfig`, `NamedDatabaseConfig` |
| `src/quadkit/sql/di/provider.py` | `DatabaseProvider` boot and registration |
| `src/quadkit/sql/repositories/base.py` | `SQLRepository` base class |
| `src/quadkit/sql/unit_of_work/base.py` | `AbstractUnitOfWork` |