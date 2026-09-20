# Testing

`quadkit-testing` lets you exercise real routes against the real ASGI
app **without starting a server or binding a port**. Tests look like
HTTP tests, but they run in-process and boot in milliseconds.

## Install

```bash
uv add --dev quadkit-testing    # or: pip install quadkit-testing
```

This also brings in `pytest` and `pytest-asyncio`. If your project does
not enable asyncio auto-mode, mark async tests explicitly — the example
below does.

The wheel carries the **web**, **db** and **ai** test clients and beds plus
the fakes and fixtures that need no private package. The `auth`, `cache`,
`events`, `search`, `storage`, `tasks`, `ui` test clients stay in the
repository until their packages publish.

## Write the test

Save as `test_first_app.py` next to the
[first app](./first-app.md)'s `first_app.py`. This file is
`docs/getting-started/examples/test_first_app.py` in this repository,
kept byte-identical with this page, and it runs in CI against the
published wheels.

<!-- snippet: examples/test_first_app.py -->
```python
"""Runnable companion to docs/getting-started/testing.md.

Tests for first_app.py — run from this directory with::

    python -m pytest test_first_app.py -v

pytest-asyncio ships with quadkit-testing; the marker below makes async
tests work whether a project enables asyncio auto-mode or not.
"""

import pytest

from first_app import create_app
from quadkit.testing import WebTestBed


@pytest.mark.asyncio
async def test_hello_default_name() -> None:
    async with WebTestBed(create_app()) as bed:
        response = bed.get("/hello")
        response.assert_status(200)
        assert response.json == {"message": "hello, world"}


@pytest.mark.asyncio
async def test_hello_with_name() -> None:
    async with WebTestBed(create_app()) as bed:
        response = bed.get("/hello", params={"name": "quadkit"})
        response.assert_status(200)
        assert response.json == {"message": "hello, quadkit"}


@pytest.mark.asyncio
async def test_docs_endpoint_is_free() -> None:
    async with WebTestBed(create_app()) as bed:
        response = bed.get("/docs")
        response.assert_status(200)
        assert "text/html" in response.headers.get("content-type", "")
```

## Run it

```bash
python -m pytest test_first_app.py -v
```

## What just happened

- `WebTestBed(app)` boots the application and wires a web test client to
  the built ASGI app. `async with` runs `setup`/`teardown` around the
  test, so the app starts and stops cleanly per test.
- `bed.get(...)` (and `post`/`put`/`delete`/`patch`) returns a
  `TestResponse` with fluent assertions — `assert_status(200)` fails
  with a readable message, and `.json`, `.text`, `.headers` expose the
  response body and metadata.
- No provider is swapped yet: these are end-to-end tests through the
  real routing, serialization, and error handling.
- When you do need to replace a dependency, the bed supports
  `override(interface, implementation)` fluently before setup — see
  [dependency injection](../concepts/dependency-injection.md#testing).

## Next steps

- The patterns scale to container-level tests (`AppTestBed`), fakes, and
  compliance suites — browse the `quadkit.testing` entry points in the
  [package README](https://github.com/dbtinoy-/quadkit/blob/main/packages/quadkit-testing/README.md).
- [Modules](../concepts/modules.md) explains how to grow beyond one
  controller file.
