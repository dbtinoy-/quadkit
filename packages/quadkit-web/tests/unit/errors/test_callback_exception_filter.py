"""Unit tests for the callable exception handler adapter and routing wiring."""

from __future__ import annotations

from typing import Any

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse

from quadkit.contracts.web.protocols import ExceptionFilterProtocol
from quadkit.web.filters.adapters import CallbackExceptionFilter
from quadkit.web.filters.builtin import DefaultExceptionFilter
from quadkit.web.filters.pipeline import FilterPipeline


class TeapotError(Exception):
    """Sample application exception."""


class FineTeapotError(TeapotError):
    """Subclass of the registered exception type."""


def _request() -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
    }
    return Request(scope)


def _build_visible_async_handler() -> Any:
    async def handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse({"brew": str(exc)}, status_code=418)

    return handler


class TestCallbackExceptionFilter:
    """Adapter presents a callable as an exception filter."""

    def test_satisfies_filter_protocol(self) -> None:
        instance = CallbackExceptionFilter(TeapotError, _build_visible_async_handler())
        assert isinstance(instance, ExceptionFilterProtocol)

    def test_can_handle_registered_type_and_subclasses(self) -> None:
        instance = CallbackExceptionFilter(TeapotError, _build_visible_async_handler())
        assert instance.can_handle(TeapotError("x")) is True
        assert instance.can_handle(FineTeapotError("x")) is True
        assert instance.can_handle(ValueError("x")) is False

    @pytest.mark.asyncio
    async def test_handle_invokes_async_handler(self) -> None:
        instance = CallbackExceptionFilter(TeapotError, _build_visible_async_handler())
        response = await instance.handle(TeapotError("short and stout"), _request())
        assert response.status_code == 418

    @pytest.mark.asyncio
    async def test_handle_invokes_sync_handler(self) -> None:
        def handler(request: Request, exc: Exception) -> JSONResponse:
            return JSONResponse({"brew": str(exc)}, status_code=418)

        instance = CallbackExceptionFilter(TeapotError, handler)
        response = await instance.handle(TeapotError("short and stout"), _request())
        assert response.status_code == 418


class TestPipelineDispatchWithAdapters:
    """Adapters participate in the router filter pipeline dispatch order."""

    @pytest.mark.asyncio
    async def test_exact_type_dispatch_prefers_adapter_over_default(self) -> None:
        pipeline = FilterPipeline(filters=[DefaultExceptionFilter()])
        pipeline.add_filter(
            CallbackExceptionFilter(TeapotError, _build_visible_async_handler())
        )
        response = await pipeline.handle(TeapotError("brewed"), _request())
        assert response.status_code == 418

    @pytest.mark.asyncio
    async def test_mro_walk_dispatches_subclass_to_registered_base(self) -> None:
        pipeline = FilterPipeline(filters=[DefaultExceptionFilter()])
        pipeline.add_filter(
            CallbackExceptionFilter(TeapotError, _build_visible_async_handler())
        )
        response = await pipeline.handle(FineTeapotError("fine brew"), _request())
        assert response.status_code == 418

    @pytest.mark.asyncio
    async def test_unregistered_type_still_falls_to_default_filter(self) -> None:
        pipeline = FilterPipeline(filters=[DefaultExceptionFilter()])
        pipeline.add_filter(
            CallbackExceptionFilter(TeapotError, _build_visible_async_handler())
        )
        response = await pipeline.handle(RuntimeError("boom"), _request())
        assert response.status_code == 500
