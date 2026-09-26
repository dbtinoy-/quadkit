# SQL Repository Demo

A focused, browser-first example of a **Quadkit SQL repository**. The demo
uses `DatabaseModule` with an in-memory SQLite database, a typed
`DatabaseProviderProtocol`, and a small `TaskRepository`. It is intentionally
about one resource: tasks.

## What you'll learn

1. `DatabaseModule.configure()` — SQLite connection lifecycle through DI
2. `DatabaseProviderProtocol` — schema setup, parameterized queries, inserts,
   updates, deletes, and health checks
3. Repository separation — SQL stays in `TaskRepository`, not the controller
4. Provider lifecycle — initialize the schema and seed rows in `boot()`
5. Browser controls — create tasks, update status, delete rows, and inspect
   SQL-backed stats

## Read in order

| # | File | What you learn |
|---|------|----------------|
| 1 | `src/taskapp/app.py` | `DatabaseModule` + `WebModule` composition |
| 2 | `src/taskapp/di/provider.py` | Resolve the database and initialize the repository |
| 3 | `src/taskapp/repository/tasks.py` | Repository queries through the database protocol |
| 4 | `src/taskapp/controllers/api.py` | Thin HTTP adapter and validation |
| 5 | `src/taskapp/ui/` | Browser task console |
| 6 | `tests/` | Real SQLite-backed composition-root coverage |

## Architecture

```
DatabaseModule.configure(SQLite)
              │
              ▼
   DatabaseProviderProtocol
              │
              ▼
       TaskRepository ──► TasksApiController
              │                    │
              └──── WebModule ◄────┘
                         │
                         ▼
                   browser console
```

The database URL is `sqlite+aiosqlite:///:memory:` so every run is isolated
and standalone. Swap the module configuration for a production database URL
without changing the repository's protocol boundary.

## Quick start

```bash
cd examples/sql-repository
uv run python -m taskapp
```

Open the URL printed by the server and use the task controls.

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/tasks/tasks` | Insert a task through the repository |
| `GET` | `/api/tasks/tasks` | List SQL-backed tasks |
| `GET` | `/api/tasks/tasks/{id}` | Read one task |
| `PUT` | `/api/tasks/tasks/{id}/status` | Update task status |
| `DELETE` | `/api/tasks/tasks/{id}` | Delete a task |
| `GET` | `/api/tasks/stats` | Query aggregate task counts |
