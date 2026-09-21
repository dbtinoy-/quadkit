# Database Tasks

SQLite CRUD behind a repository class, wired through DI — the canonical
starter for the repository pattern. Handlers call the synchronous driver
via `asyncio.to_thread`; swap in `aiosqlite`/`asyncpg` and `await`
directly when moving to a server database.

**Demonstrates:** a provider-owned singleton (the `TaskRepository`),
fail-fast boot checks, CRUD routes with `201/404/422` semantics mapped
by the Result bridge, and persistence tests that reopen the same
database file in a fresh app instance.

## Layout

```
src/database_tasks/
├── app.py             # composition root
├── main.py            # serve() with try/finally app.stop()
├── config.py          # DatabaseTasksConfig (db_path)
├── controllers/api.py # TasksController — CRUD routes
├── services/repository.py # TaskRepository (sqlite3 + health)
└── di/provider.py     # opens in boot(), closes in shutdown()
```

## Run

```bash
pip install quadkit[web]
QK_DATABASE_TASKS__DB_PATH=tasks.db PYTHONPATH=src python -m database_tasks
curl -X POST localhost:8123/tasks -H 'content-type: application/json' \
  -d '{"title": "write docs"}'
curl localhost:8123/tasks
```

The database path is `database_tasks.db_path` (`:memory:` by default).

## Test

```bash
PYTHONPATH=src pytest tests/
```

The suite also exercises reliability: persistence across restarts and
boot failure injection (an unwritable DB path fails fast at boot, named
in the error).
