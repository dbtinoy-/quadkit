"""Feature tour: exception handling — one vocabulary for thrown errors.

Raising your own ``DomainError`` from a handler needs no wiring at all:
the exception filters translate it into an RFC 7807 problem details
response — machine-readable ``type`` URN, human-readable ``title`` and
``detail``, error code and a see-also link included. When an exception
type deserves its own translation, ``WebModule.configure`` accepts a
plain ``{ExceptionType: handler}`` mapping: async or sync callables in
the Starlette ``(request, exc)`` convention, dispatched by exact type
first and by inheritance afterwards, and — when they name a framework
family such as ``DomainError`` — taking precedence over the built-in
problem-details translation.
"""

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse

from quadkit import Application, DomainError
from quadkit.testing import WebTestBed
from quadkit.web import Controller, WebModule, get
from quadkit.web.config.top_level import WebConfig
from quadkit.web.security.config.top_level import SecurityConfig


class CheckoutError(DomainError):
    """Payment declined at the terminal."""


class TeapotError(Exception):
    """A coffee order reaches the teapot."""


class RareTeapotError(TeapotError):
    """An even rarer coffee order."""


async def teapot_handler(request: Request, exc: TeapotError) -> JSONResponse:
    return JSONResponse({"brew": str(exc)}, status_code=418)


async def checkout_handler(request: Request, exc: CheckoutError) -> JSONResponse:
    return JSONResponse({"declined": str(exc)}, status_code=402)


class Shop(Controller):
    @get("/declined")
    async def declined(self) -> None:
        raise CheckoutError("card declined")

    @get("/teapot")
    async def teapot(self) -> None:
        raise TeapotError("short and stout")

    @get("/rare-teapot")
    async def rare_teapot(self) -> None:
        raise RareTeapotError("reserved for ceremonial brews")


def make_app(**kwargs: object) -> Application:
    app = Application()
    app.add_module(
        WebModule.configure(
            controllers=[Shop],
            web_config=WebConfig(security=SecurityConfig(enable_csrf=False)),
            **kwargs,
        )
    )
    return app


@pytest.mark.asyncio
async def test_thrown_domain_errors_become_problem_details_without_wiring() -> None:
    async with WebTestBed(make_app()) as bed:
        response = bed.get("/declined")
        assert response.status_code == 400
        assert response.headers["content-type"].startswith("application/problem+json")
        problem = response.json
        assert problem["type"].startswith("urn:quadkit:")
        assert problem["title"] == "Bad Request"
        assert problem["status"] == 400
        # The domain message arrives verbatim, error code attached.
        assert "card declined" in problem["detail"]
        assert "QK_ERR" in problem["detail"]


@pytest.mark.asyncio
async def test_configured_exception_handlers_translate_their_own_types() -> None:
    app = make_app(exception_handlers={TeapotError: teapot_handler})
    async with WebTestBed(app) as bed:
        response = bed.get("/teapot")
        assert response.status_code == 418
        assert response.json == {"brew": "short and stout"}


@pytest.mark.asyncio
async def test_handler_mapping_dispatches_by_inheritance_and_overrides_defaults() -> None:
    app = make_app(
        exception_handlers={
            TeapotError: teapot_handler,
            CheckoutError: checkout_handler,
        }
    )
    async with WebTestBed(app) as bed:
        # A registered base type answers for its subclasses.
        subclass = bed.get("/rare-teapot")
        assert subclass.status_code == 418
        assert subclass.json == {"brew": "reserved for ceremonial brews"}

        # Naming a DomainError type routes it to your handler instead of
        # the built-in problem-details translation.
        overridden = bed.get("/declined")
        assert overridden.status_code == 402
        assert "card declined" in overridden.json["declined"]
