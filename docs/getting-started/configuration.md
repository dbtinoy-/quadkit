# Configuration

Quadkit configuration is **typed**: each section of your
`application.yaml` maps 1:1 to a validated config model, and the
framework validates the file against those models at boot time. Unknown
or mistyped keys fail fast instead of silently doing nothing.

## `application.yaml`

The application reads `application.yaml` from the current working
directory at start. A minimal web service needs almost nothing:

```yaml
name: hello-service
version: 0.1.0
description: "My first quadkit service"

web:
  server:
    host: 0.0.0.0
    port: 8000
    backend: granian
```

- `name`, `version`, `description` — application metadata, surfaced in
  logs and health output.
- `web.server.host` / `web.server.port` — bind address. Explicit
  `run_server(app, host=..., port=...)` arguments take precedence for
  that call; the file is what the defaults come from.
- `web.server.backend` — pin the server backend (`granian`, `uvicorn`,
  or `hypercorn` depending on the installed extras). When absent, the
  resolver auto-prefers Granian, then Uvicorn.

When `application.yaml` does not exist, the app boots on framework
defaults and logs a hint telling you so — that is what the
[first app](./first-app.md) does.

## Environment overrides

Every typed key can also be set from the environment with the
`QK_<SECTION>__<KEY>` convention — double underscores are the nesting
delimiter:

```bash
export QK_WEB__SERVER__PORT=9000
export QK_WEB__SERVER__BACKEND=uvicorn
python first_app.py
```

`QK_*` environment variables override the YAML values. This keeps
`application.yaml` safe to commit (defaults and topology) while secrets
and per-environment values come from the process environment.

## See it all at once

The public examples ship fully commented configuration files that show
every available key with its default — start with
[example-hub's application.yaml](https://github.com/dbtinoy-/quadkit/blob/main/examples/example-hub/application.yaml),
whose preamble also documents the `QK_` override pattern.

Next: [testing](./testing.md).
