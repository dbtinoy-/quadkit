# quadkit-cli reference

The development command line: project scaffolding, generators, and dev
commands. It installs the `quadkit` console script.

- **Install**: `pip install quadkit-cli` · Python `>= 3.11`
- **Version** (lockstep with all thirteen distributions): `0.0.46`
  → [stability policy](./stability.md)
- **Issues**: <https://github.com/dbtinoy-/quadkit/issues>

## Extras

Verified against the package's `pyproject.toml`: `[dev]`, `[test]`, and
`[all]` (both).

## The `quadkit` command

Global options: `--json` (machine-readable output), `--quiet`, `--debug`,
`--no-color`, and `--config <path>` to point at a specific
`application.yaml`.

Commands (from `quadkit --help`):

| Command | Purpose |
| --- | --- |
| `quadkit new project` | Create a new Quadkit project |
| `quadkit new module` | Create a bounded context inside a modular project |
| `quadkit new package` | Scaffold a new `quadkit-*` extension package |
| `quadkit init` | Initialize Quadkit in an existing project |
| `quadkit add` | Add a provider to the project |
| `quadkit run` | Smart runner — auto-detects the factory, sets the profile |
| `quadkit dev` | Development server and tools |
| `quadkit gen` | Code generation |
| `quadkit test` / `quadkit lint` | Project tests / linting |
| `quadkit db` | Database management commands |
| `quadkit events` | Event schema management |
| `quadkit config` | Configuration management |
| `quadkit inspect` | Inspect runtime state |
| `quadkit shell` | Interactive Python REPL |
| `quadkit project` | Project management (test, lint, routes) |
| `quadkit contrib` / `quadkit system` / `quadkit version` | Introspection and versions |

`quadkit run` in detail, since it is the serving entry point:

```bash
quadkit run my_app.app:create_app \
    --host 0.0.0.0 --port 8000 \
    --workers 4 --no-reload --server granian
```

Target format is `module:attribute` and auto-detects when omitted;
options mirror the `web.server` configuration: `--host`, `--port`,
`--reload/--no-reload`, `--workers`, `--profile` (sets `QK_PROFILE`),
and `--server` (`granian`, `uvicorn`, or `hypercorn`). Hot reload
defaults **on** — pass `--no-reload` in production. See
[production deployment](../guides/production-deployment.md).
