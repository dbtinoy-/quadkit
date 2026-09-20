"""Feature tour: request-scoped context.

Core side: `request_context(registry, ...)` sets typed contextvars for the
scope of a `with` block and restores them on exit — correlation ids ride
through `await` points (and into tasks that inherit the context) with zero
parameter plumbing. The registry is typed and fail-fast: keys must be
pre-registered (`create_default_context().registry` ships the standard set),
so a typo surfaces at write time, never in a log warehouse.

Web side: `RequestContextMiddleware` (on by default) runs the same primitive
around every request: it honours/propagates `X-Request-ID`, attaches tenant
ids from `X-Tenant-ID`, exposes the live context on
`request.state.request_context`, and echoes the id back on the response
headers. One pattern from CLI batch jobs to HTTP handlers.
"""

import asyncio

import pytest
from starlette.requests import Request

from quadkit import Application, request_context
from quadkit.primitives.context import (
    CORRELATION_ID,
    REQUEST_ID,
    create_default_context,
)
from quadkit.testing import WebTestBed
from quadkit.web import Controller, WebModule, get

# --------------------------------------------------------------------------
# Core: scoped contextvars with restore-on-exit
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_context_scopes_and_restores() -> None:
    registry = create_default_context().registry

    assert registry.get_typed(REQUEST_ID) is None

    with request_context(
        registry, request_id="req-42", correlation_id="corr-7"
    ) as ctx:
        assert registry.get_typed(REQUEST_ID) == "req-42"
        assert registry.get_typed(CORRELATION_ID) == "corr-7"

        # Tasks created inside the scope inherit the live contextvars.
        async def read_ids() -> tuple[str | None, str | None]:
            await asyncio.sleep(0)
            return (
                registry.get_typed(REQUEST_ID),
                registry.get_typed(CORRELATION_ID),
            )

        assert await asyncio.create_task(read_ids()) == ("req-42", "corr-7")
        assert ctx.request_id == "req-42"

    # Exiting restores the outer state.
    assert registry.get_typed(REQUEST_ID) is None
    assert registry.get_typed(CORRELATION_ID) is None


@pytest.mark.asyncio
async def test_nested_scopes_override_and_unwind() -> None:
    registry = create_default_context().registry

    with request_context(registry, request_id="outer"):
        with request_context(registry, request_id="inner"):
            assert registry.get_typed(REQUEST_ID) == "inner"
        assert registry.get_typed(REQUEST_ID) == "outer"


# --------------------------------------------------------------------------
# Web: the same primitive wired around every HTTP request
# --------------------------------------------------------------------------


class TraceController(Controller):
    prefix = "/trace"

    @get("/who")
    async def who(self, request: Request) -> dict:
        ctx = request.state.request_context
        return {
            "request_id": ctx.request_id,
            "tenant_id": ctx.tenant_id,
        }


def create_app() -> Application:
    app = Application()
    app.add_module(WebModule.configure(controllers=[TraceController]))
    return app


@pytest.mark.asyncio
async def test_web_request_context_propagates_headers() -> None:
    async with WebTestBed(create_app()) as bed:
        seen = bed.get(
            "/trace/who",
            headers={"x-request-id": "req-42", "x-tenant-id": "acme"},
        )
        assert seen.status_code == 200
        assert seen.json == {"request_id": "req-42", "tenant_id": "acme"}
        # The id is echoed back for the caller's logs.
        assert seen.headers["x-request-id"] == "req-42"

        # Absent header → the framework mints one.
        minted = bed.get("/trace/who")
        generated = minted.json["request_id"]
        assert generated
        assert generated != "req-42"
        assert minted.headers["x-request-id"] == generated
