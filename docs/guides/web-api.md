# Building a web API

Beyond the [first app](../getting-started/first-app.md), a real API needs
typed inputs: path parameters, query strings, validated request bodies,
and intentional status codes. Quadkit binds all of them from method
signatures — this page is a tour of the binding rules, backed by a
runnable example.

The example below is `docs/guides/examples/web_api_app.py` in this
repository, kept byte-identical with this page, with tests executed in
CI. Run it yourself from `docs/guides/examples`:

```bash
pytest test_web_api_app.py
```

## The example application

<!-- snippet: examples/web_api_app.py -->
```python
"""Runnable companion to docs/guides/web-api.md.

The full notes API used by the guide: typed route parameters, query
binding, a validated pydantic request body, and responses derived from
the return value. Run the tests from this directory:

    pytest test_web_api_app.py
"""

from pydantic import BaseModel

from quadkit import Application
from quadkit.web import Controller, WebModule, body, get, path, post, query


class NoteIn(BaseModel):
    """Request body for creating a note; validated before the route runs."""

    title: str
    body: str = ""


_NOTES: dict[int, dict] = {1: {"title": "first", "body": "shipped with the app"}}


class NotesController(Controller):
    @get("/notes/{note_id}")
    async def read_note(self, note_id: int, verbose: bool = False) -> dict:
        """``{note_id}`` binds by name and validates as ``int``.

        Plain keyword arguments bind from the query string by name.
        """
        if note_id not in _NOTES:
            return {}  # kept simple here; real 404s: see error-handling.md
        return {"id": note_id, "verbose": verbose, **_NOTES[note_id]}

    @get("/notes")
    async def list_notes(self, limit: int = 10) -> dict:
        """Query parameters convert to the annotated type (``int``)."""
        items = [{"id": k, **v} for k, v in sorted(_NOTES.items())][:limit]
        return {"count": len(items), "items": items}

    @post("/notes", status_code=201)
    async def create_note(self, payload: NoteIn = body()) -> dict:
        """``body()`` binds the whole request body to a pydantic model."""
        new_id = max(_NOTES, default=0) + 1
        _NOTES[new_id] = payload.model_dump()
        return {"id": new_id, **payload.model_dump()}


def create_app() -> Application:
    """Assemble the application from the web module and one controller."""
    app = Application()
    app.add_modules([WebModule.configure(controllers=[NotesController])])
    return app


app = create_app()
```

## Binding rules

**Route decorators.** `@get`, `@post`, `@put`, `@patch`, `@delete` take a
path and build the route from the method signature. The example's
`status_code=201` is a route decorator option; the default success
status is `200`.

**Path parameters.** `{note_id}` in the pattern binds to the method
argument of the same name and converts to the annotated type — a
non-integer `note_id` never reaches your code.

**Query parameters.** Plain keyword arguments (`verbose: bool = False`,
`limit: int = 10`) bind from the query string by name and convert to the
annotation. Missing values fall back to the default. `query(alias=...)`
renames the wire name when it differs from the Python name.

**Request bodies.** `payload: NoteIn = body()` binds the *whole* request
body to a [pydantic](https://docs.pydantic.dev/) `BaseModel`.
Validation failures never reach the route: the client gets a
`422` problem response with one entry per bad field, for example
`{"field": "payload.title", "code": "missing"}`.

**Other sources.** Matching decorators exist for every input channel:
`header(alias=...)`, `cookie(...)`, `form(...)`, `path(...)`, and
`query(...)` are all importable from `quadkit.web`.

## Documentation comes with it

Every registered controller feeds the generated OpenAPI: interactive
Swagger UI at `/docs`, Redoc at `/redoc`, and the schema itself at
`/openapi.json` — no extra wiring.

## A word on CSRF before you POST

The framework enables cookie-based CSRF protection by default
(`web.security.enable_csrf` defaults to `true`). A bare
`curl -X POST` (or a test client POST) against a default-configured app
therefore answers `403 csrf_error: missing token`. For JSON APIs
consumed by non-browser clients, disable it explicitly in
`application.yaml` — which is exactly what the shipped
`docs/guides/examples/application.yaml` does, with a comment explaining
why. Browser-facing apps should keep the default and pass the token
cookie/header (`csrf_token` / `X-CSRF-Token` by default).

## Next steps

- [Error handling](./error-handling.md) — return `Result`s or raise
  `HTTPError`; every failure is a problem-response.
- [Middleware](./middleware.md) — wrap the whole application, ASGI-style.
- [Dependency overrides](./dependency-overrides.md) — constructor
  injection in controllers and test doubles.
