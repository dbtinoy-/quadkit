"""The application-wide exception filter pipeline, end to end.

plans/09182026 S-03 removed the module-level ``filter_pipeline`` global. The
application-wide pipeline is now a container singleton built from
``WebProvider(filters=[...])`` and injected into the request path. These tests
boot a real application and pin the ordering that makes it reachable:

1. route-level filters (``@use_filters``),
2. the application-wide pipeline, but only for exceptions it claims,
3. the router's built-in defaults, which own every mapped error and end in
   the structured 500.
"""

from __future__ import annotations

from typing import Any

import pytest
from starlette.testclient import TestClient

from quadkit.app.base import Application
from quadkit.web import Controller, get
from quadkit.web.config import RateLimitConfig, WebConfig
from quadkit.web.di.provider import WebProvider
from quadkit.web.filters.pipeline import FilterPipeline
from quadkit.web.transport.responses import JSONResponse


class TelemetryError(Exception):
    """Error type no built-in filter claims."""


class ClaimTelemetryFilter:
    """Application-wide filter for :class:`TelemetryError`."""

    def can_handle(self, exc: Exception) -> bool:
        return isinstance(exc, TelemetryError)

    async def handle(self, exc: Exception, _request: Any) -> JSONResponse:
        return JSONResponse(
            content={"handled_by": "application-wide", "detail": str(exc)},
            status_code=418,
        )


class NeverClaimsFilter:
    """Application-wide filter that claims nothing."""

    def can_handle(self, exc: Exception) -> bool:
        return False

    async def handle(
        self, exc: Exception, _request: Any
    ) -> JSONResponse:  # pragma: no cover
        raise AssertionError("handle() must not run for an unclaimed exception")


class ProbeController(Controller):
    """Routes that raise the error types under test."""

    @get("/telemetry")
    async def telemetry(self) -> dict:
        raise TelemetryError("probe")

    @get("/boom")
    async def boom(self) -> dict:
        raise RuntimeError("unmapped failure")


async def _boot(filters: list[Any]) -> tuple[Any, TestClient]:
    """Boot an app whose provider carries ``filters``."""
    app = Application(name="global-filter-probe")
    web = WebProvider(
        web_config=WebConfig(rate_limit=RateLimitConfig(enabled=False)),
        controllers=[ProbeController],
        filters=filters,
    )
    await web.register(app.container)
    await web.boot(app.container)
    assert web.starlette is not None
    return web, TestClient(web.starlette)


def test_can_handle_matches_what_handle_would_pick() -> None:
    """``FilterPipeline.can_handle`` mirrors the dispatch in ``handle``."""
    from quadkit.web.filters import DefaultExceptionFilter

    empty = FilterPipeline()
    assert empty.can_handle(TelemetryError("x")) is False

    pipeline = FilterPipeline(filters=[ClaimTelemetryFilter()])
    assert pipeline.can_handle(TelemetryError("x")) is True
    assert pipeline.can_handle(RuntimeError("x")) is False

    defaults = FilterPipeline(filters=[DefaultExceptionFilter()])
    assert defaults.can_handle(RuntimeError("x")) is False


@pytest.mark.asyncio
async def test_application_wide_filter_answers_the_errors_it_claims() -> None:
    """A provider-registered filter handles its exception type on the wire."""
    web, client = await _boot([ClaimTelemetryFilter()])

    assert web.router.global_pipeline is not None
    assert len(web.router.global_pipeline.filters) == 1

    with client:
        response = client.get("/telemetry")

    assert response.status_code == 418
    assert response.json() == {"handled_by": "application-wide", "detail": "probe"}
    assert response.headers["content-type"] == "application/json"


@pytest.mark.asyncio
async def test_framework_defaults_still_own_the_errors_they_map() -> None:
    """An unclaimed exception keeps the built-in problem document."""
    _web, client = await _boot([NeverClaimsFilter()])

    with client:
        response = client.get("/boom")

    assert response.status_code == 500
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["type"] == "urn:quadkit:internal-error"


@pytest.mark.asyncio
async def test_empty_pipeline_leaves_the_defaults_in_charge() -> None:
    """With no provider filters the request path behaves as before."""
    web, client = await _boot([])

    assert web.router.global_pipeline is not None
    assert web.router.global_pipeline.filters == []

    with client:
        response = client.get("/boom")

    assert response.status_code == 500
    assert response.json()["type"] == "urn:quadkit:internal-error"
