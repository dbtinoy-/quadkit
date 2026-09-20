"""One error contract: every failure answers ``application/problem+json``.

A client that keys on the media type or on the problem document's fields must
see the same shape whichever way a request failed. This module boots a default
application and exercises the four paths that used to disagree:

- a domain error raised from a route,
- a request-validation failure,
- an unhandled exception,
- an unknown route (Starlette's own handler).

The debug-only extensions (exception type, traceback) are asserted too, so a
production app is pinned to the generic detail.
"""

from __future__ import annotations

import asyncio

import pytest

from quadkit import Application
from quadkit import serialization as json
from quadkit.web import Controller, get, post
from quadkit.web.exceptions import NotFoundError

PROBLEM_MEDIA_TYPE = "application/problem+json"


class ContractController(Controller):
    """One route per failure mode the contract covers."""

    @get("/ok")
    async def ok(self) -> dict:
        return {"ok": True}

    @get("/domain-error")
    async def domain_error(self) -> dict:
        raise NotFoundError("resource is gone")

    @get("/unhandled")
    async def unhandled(self) -> dict:
        raise RuntimeError("kaboom: secret=abc")

    @post("/validated")
    async def validated(self, count: int) -> dict:
        return {"count": count}

    @post("/csrf")
    async def csrf(self) -> dict:
        return {"ok": True}


def _bed(*, csrf: bool = False):
    """Boot the contract app behind the public test bed."""
    from quadkit.testing import WebTestBed

    app = Application(name="error-contract")
    app.add_modules([_web_module(csrf=csrf)])
    return WebTestBed(app)


def _web_module(*, csrf: bool = False):
    """The contract app; CSRF is off unless a test drives that rejection."""
    from quadkit.web import WebModule
    from quadkit.web.config import WebConfig
    from quadkit.web.security.config import CSRFConfig, SecurityConfig

    web_config = WebConfig(security=SecurityConfig(csrf=CSRFConfig(enabled=csrf)))
    return WebModule.configure(
        controllers=[ContractController],
        web_config=web_config,
    )


def _problem(response) -> dict:
    """Assert the problem media type and return the parsed document."""
    assert response.headers["content-type"].startswith(PROBLEM_MEDIA_TYPE), (
        f"expected {PROBLEM_MEDIA_TYPE}, got {response.headers['content-type']}"
    )
    return json.loads(response.text)


def _run(callable_, *, csrf: bool = False):
    """Run one bed interaction against a freshly booted app."""

    async def _main():
        bed = _bed(csrf=csrf)
        await bed.__aenter__()
        try:
            return callable_(bed)
        finally:
            await bed.__aexit__(None, None, None)

    return asyncio.run(_main())


def test_domain_error_uses_the_problem_contract() -> None:
    """A raised domain error renders RFC 7807 with its type and status."""
    response = _run(lambda bed: bed.get("/domain-error"))
    body = _problem(response)

    assert response.status_code == 404
    assert body["type"] == "urn:quadkit:not-found"
    assert body["status"] == 404
    assert body["detail"] == "resource is gone"


def test_validation_failure_uses_the_problem_contract() -> None:
    """A request-validation failure keeps the shape, with ``errors[]``."""
    response = _run(lambda bed: bed.post("/validated", json={"count": "not-a-number"}))
    body = _problem(response)

    assert response.status_code == 422
    assert body["status"] == 422
    assert body["type"] == "urn:quadkit:validation-error"
    assert body["errors"]


def test_unhandled_exception_uses_the_problem_contract() -> None:
    """An unhandled exception answers the problem shape with a generic detail."""
    response = _run(lambda bed: bed.get("/unhandled"))
    body = _problem(response)

    assert response.status_code == 500
    assert body["type"] == "urn:quadkit:internal-error"
    assert body["status"] == 500
    assert body["detail"] == "An unexpected error occurred"
    # No internals leak in a non-debug response.
    assert "secret" not in response.text
    assert "traceback" not in body
    assert "exception_type" not in body


def test_unknown_route_uses_the_problem_contract() -> None:
    """Starlette's own 404 renders the problem shape, not ``text/plain``."""
    response = _run(lambda bed: bed.get("/definitely-not-a-route"))
    body = _problem(response)

    assert response.status_code == 404
    assert body["type"] == "urn:quadkit:not-found"
    assert body["status"] == 404
    assert body["title"] == "Not Found"


def test_unsupported_method_uses_the_problem_contract() -> None:
    """A 405 renders the problem shape and keeps the ``Allow`` header."""
    response = _run(lambda bed: bed.put("/ok"))
    body = _problem(response)

    assert response.status_code == 405
    assert body["type"] == "urn:quadkit:method-not-allowed"
    assert body["status"] == 405
    assert "allow" in {key.lower() for key in response.headers}


def test_no_path_answers_the_legacy_envelope() -> None:
    """Every failure path shares one media type across the whole app."""
    responses = _run(
        lambda bed: [
            bed.get("/domain-error"),
            bed.post("/validated", json={"count": "nope"}),
            bed.get("/unhandled"),
            bed.get("/definitely-not-a-route"),
            bed.put("/ok"),
        ]
    )
    media_types = {r.headers["content-type"].split(";")[0] for r in responses}

    assert media_types == {PROBLEM_MEDIA_TYPE}
    for response in responses:
        assert "success" not in response.text


def test_debug_extensions_are_gated_behind_debug_mode() -> None:
    """Debug adds the exception type and traceback, and only in debug."""
    from quadkit.web.filters.pipeline import FilterPipeline
    from quadkit.web.transport.responses import JSONResponse

    async def _handle(pipeline: FilterPipeline):
        return await pipeline.handle(RuntimeError("kaboom"), request=None)

    debug_response = asyncio.run(_handle(FilterPipeline(debug=True)))
    assert isinstance(debug_response, JSONResponse)
    debug_body = json.loads(debug_response.body)
    assert debug_body["exception_type"] == "RuntimeError"
    assert "traceback" in debug_body

    quiet_body = json.loads(asyncio.run(_handle(FilterPipeline(debug=False))).body)
    assert "exception_type" not in quiet_body
    assert "traceback" not in quiet_body


def test_debug_mode_reads_only_the_environment() -> None:
    """``is_debug_mode()`` is env-gated, so production is never debug here."""
    from quadkit.logging import debug

    assert debug.is_debug_mode() is False  # QK_DEBUG is unset in the test env


@pytest.mark.parametrize("path", ["/domain-error", "/unhandled", "/nope"])
def test_accept_header_does_not_change_the_json_contract(path: str) -> None:
    """A browser's ``Accept`` default still receives the problem document."""
    response = _run(
        lambda bed: bed.get(path, headers={"Accept": "text/html,application/xhtml+xml"})
    )
    body = _problem(response)

    assert body["status"] == response.status_code


def test_csrf_rejection_uses_the_problem_contract() -> None:
    """The CSRF middleware sits above the pipeline and renders the same shape."""
    response = _run(lambda bed: bed.post("/csrf", json={}), csrf=True)
    body = _problem(response)

    assert response.status_code == 403
    assert body["type"] == "urn:quadkit:csrf-error"
    assert body["status"] == 403
    assert "missing token" in body["detail"]
    assert "success" not in response.text
