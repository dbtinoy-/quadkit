# quadkit-testing reference

Test harnesses for Quadkit applications: in-process test beds that boot
the real application (or substitute its bindings), plus assertion-minded
response wrappers. Core dependencies are the pytest toolchain
(`pytest`, `pytest-asyncio`, `pytest-cov`, `pytest-mock`) plus `quadkit`
and `quadkit-contracts`.

- **Install**: `pip install quadkit-testing` · Python `>= 3.11`
- **Version** (lockstep with all thirteen distributions): `0.0.42`
  → [stability policy](./stability.md)
- **Issues**: <https://github.com/dbtinoy-/quadkit/issues>

## Extras

Verified against the package's `pyproject.toml`:

| Extra | Contents |
| --- | --- |
| `[web]` | `httpx` + Starlette — the web test client (`WebTestBed`) |
| `[db]` | `aiosqlite`, `asyncpg` — async database test helpers |
| `[integration]` | service clients for integration tests (Redis, Mongo, Kafka, Elasticsearch, Neo4j, Qdrant, Postgres, SQLite) |
| `[dev]` | `ruff`, `mypy`, `black` |

The published distribution ships the `ai`, `db` and `web` test clients and
beds plus the fakes and fixtures that need no private package. The `auth`,
`cache`, `events`, `search`, `storage`, `tasks`, `ui` test clients stay in
the repository until their packages publish.

## Public entry points

```python
from quadkit.testing import AppTestBed, WebTestBed
```

### `AppTestBed` — application-level tests

Async context managers that boot the application without HTTP:

```python
async def test_service() -> None:
    async with AppTestBed.from_factory(create_app) as bed:
        service = await bed.app.container.resolve(MyService)
```

- `AppTestBed.from_factory(factory, overrides=None)` — `factory` is a
  callable or a `"my_app.app:create_app"` dotted string; `overrides`
  maps service types to test doubles applied before boot.
- `AppTestBed.from_app(app)` — same bed around an assembled app.

### `WebTestBed` — HTTP-level tests

```python
async def test_read_note() -> None:
    async with WebTestBed(create_app()) as bed:
        response = bed.get("/notes/1", params={"verbose": "true"})
        response.assert_status(200)
        assert response.json["title"] == "first"
```

- `WebTestBed(app_or_provider, raise_server_exceptions=True)` and the
  verb methods `get`, `post`, `put`, `patch`, `delete`
  (httpx-compatible kwargs: `params`, `json`, `headers`, `content`).
- `bed.override(Contract, implementation)` — chainable binding
  substitution; register **before** entering the context (before boot).
- `TestResponse` — `status_code`, `headers`, `text`, `json`
  (a property, not a method), and assertions `assert_status`,
  `assert_json`, `assert_json_path`, `assert_header`.

The beds boot a *real* application — configuration validation, provider
lifecycles, container freeze all run — so a green suite doubles as a
configuration regression check.

Guides: [testing quickstart](../getting-started/testing.md) ·
[dependency overrides](../guides/dependency-overrides.md).
