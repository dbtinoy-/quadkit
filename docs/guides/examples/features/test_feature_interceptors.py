"""Feature tour: interceptors — NestJS-style before/after around handlers.

An interceptor wraps every handler invocation: code before
`await next_handler.handle()` runs on the way in; code after runs on the
way out and may transform the result. Scope is declarative, both levels
composable: `@use_interceptors(...)` on a handler or controller covers
those routes; the app-wide `InterceptorPipeline` singleton covers every
route — register there once, no per-route decorators.
"""

from typing import Any

import pytest

from quadkit import Application
from quadkit.testing import WebTestBed
from quadkit.web import Controller, WebModule, get, use_interceptors
from quadkit.web.interceptors.builtin.transform import TransformInterceptor
from quadkit.web.interceptors.pipeline import InterceptorPipeline
from quadkit.web.protocols import CallHandlerProtocol, ExecutionContextProtocol

VISITS: list[str] = []


class MethodTagInterceptor:
    """Observes the request on the way in, enriches the result on the way out."""

    async def intercept(
        self,
        context: ExecutionContextProtocol,
        next_handler: CallHandlerProtocol,
    ) -> Any:
        VISITS.append(f"{context.request.method} {context.request.url.path}")
        result = await next_handler.handle()
        if isinstance(result, dict):
            result = {**result, "intercepted": True}
        return result


class PingController(Controller):
    @get("/ping")
    async def ping(self) -> dict:
        return {"pong": True}

    @get("/enveloped")
    @use_interceptors(
        TransformInterceptor(transform=lambda data: {"success": True, "data": data})
    )
    async def enveloped(self) -> dict:
        return {"value": 7}


def create_app() -> Application:
    app = Application()
    app.add_module(WebModule.configure(controllers=[PingController]))
    return app


@pytest.mark.asyncio
async def test_app_wide_interceptors_cover_every_route() -> None:
    VISITS.clear()
    async with WebTestBed(create_app()) as bed:
        pipeline = await bed.resolve(InterceptorPipeline)
        pipeline.add_interceptor(MethodTagInterceptor())

        assert bed.get("/ping").json == {"pong": True, "intercepted": True}
        # App-wide interceptors run outermost: the envelope is built by the
        # handler-level interceptor first, then the app-wide one enriches.
        assert bed.get("/enveloped").json == {
            "success": True,
            "data": {"value": 7},
            "intercepted": True,
        }

        # Both invocations were observed on the way in, in order.
        assert VISITS == ["GET /ping", "GET /enveloped"]


@pytest.mark.asyncio
async def test_handler_level_interceptors_scope_to_their_route() -> None:
    async with WebTestBed(create_app()) as bed:
        # Handler-attached TransformInterceptor never touches /ping.
        assert bed.get("/ping").json == {"pong": True}
        assert bed.get("/enveloped").json == {
            "success": True,
            "data": {"value": 7},
        }
