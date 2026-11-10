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

## Generated health checks are unfinished probes

The SQL-owned `health` generator emits a `quadkit.monitor.health.HealthCheck`
subclass, not a working database or resource probe. Its async `check()` returns
canonical `HealthCheckResult` with `UNHEALTHY`, an explicit not-implemented error,
and `details={"implementation_required": True}` until application code replaces
it with a real probe. `critical` metadata is preserved; it does not implement
or register the check.

Implement the dependency check and register its `check` callable with your
application's health checker (for example, `HealthChecker.add(name, probe.check)`).
Generation/import alone does neither. `@INTENT`/`@TODO` comments make this custom
work visible to Playground Completion; those markers are not runtime acceptance.
The framework's existing `/health` endpoint does not prove this custom probe is
registered. This contract concerns generated classes, not every SQL CLI health
contribution or database-provider health implementation.

## Database connectivity contribution

`cli.checks.check_database_connection(container)` now resolves the configured
`DatabaseProviderProtocol` through a **booted** container and awaits its
`health_check(timeout=5.0)`. It preserves canonical provider health evidence,
including non-healthy states. Resolution and probing share a five-second deadline;
exceptions or malformed results become UNHEALTHY without copying raw exception
text into the failure result. Caller cancellation propagates. The caller owns
provider/application lifecycle; this callback neither reads database URLs nor
creates a replacement provider. It does **not** verify migration state.

**Explicit runner integration (local CLI0.0.50 source):** from an importable
application project, run `quadkit system health --app my_api.app:app --check
sql:database_connection --strict` (as one shell command). The CLI starts the
selected fresh Application, passes its container to this async callback and stops
it afterwards. Normal provider boot may have side effects; use an approved
environment. This path is demonstrated with flat/modular generated anonymous-
action applications and local SQLite, not installed wheels or every backend.
It does not register generated custom probe classes or verify migrations. Other
CLI health contributions still need their own canonical-contract evidence.

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

## Transaction boundaries

The driver transaction context joins an existing transaction in the same task;
it is not a savepoint. A child task inheriting that transaction context is
refused on managed driver acquisition, query and transaction entry, including
after the owner finishes. This includes tasks created by helpers such as
`asyncio.wait_for`; use same-task operations within a transaction. A
`DatabaseService.execute` refusal is returned as a failed `QueryResult`, so
callers must check `success`. Unrelated workers need an independent context and
must not be awaited while their parent holds the shared connection lock.

For the standard driver manager, same-task managed acquisitions during a
transaction borrow its physical connection instead of a second pool lease;
the outer transaction owns release. Manual transaction queries also borrow
the manual connection. This does not cover raw handles, separate scoped-
connection paths, custom managers, or direct users of a shared pool. Do not use
those paths concurrently with managed transactions. Manual transactions open a
separate connection, which is a separate database for in-memory SQLite.

After a transaction-end hook returns, known raw SQLite/PostgreSQL connections
are checked for a new physical transaction. If found, the manager is
quarantined and close is attempted; a preceding commit remains committed.
Unknown wrappers are not checked, failed close remains unsafe, and hook writes
that already autocommitted are not undone. Hooks must not be treated as part
of the transaction that has already ended.

Before an outer transaction starts, the SQLite and PostgreSQL drivers refuse
an already-active physical transaction on exact raw `aiosqlite.Connection` and
`asyncpg.Connection` objects. The original raw transaction is not committed or
rolled back. This check does not cover custom wrappers, other drivers, manual
transaction APIs, or raw users that race after the check; it is not a general
physical-ownership guarantee.

On an escaping exception or cancellation, the outer context attempts rollback
before releasing its managed connection. Failed cleanup or transaction-end
hooks quarantine that connection manager and attempt close. Quarantine does not
revoke raw handles or independent shared-pool users. An interrupted commit may
already have succeeded: reconcile its result using the application's durable
idempotency protocol rather than assuming rollback.

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