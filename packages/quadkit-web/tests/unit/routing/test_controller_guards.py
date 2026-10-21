"""Controller-level guards run before parameter binding, and answer in their own words.

Found by an application whose every action door required a tenant scope:
with guards only readable off the handler and the pipeline ignoring
``handle_rejection``, an unauthenticated request with a malformed body got
a 422 describing the schema instead of the application's 403.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from httpx import ASGITransport, AsyncClient
from quadkit.testing import TestEnvironment
from quadkit.web import Controller, WebProvider, post
from quadkit.web.config import CSRFConfig, RateLimitConfig, SecurityConfig, WebConfig
from quadkit.web.security.guards import use_guards
from quadkit.domain import DomainModel
from starlette.responses import JSONResponse

try:
    import pytest_asyncio
except ImportError:  # pragma: no cover
    pytest_asyncio = None


@dataclass
class Adjust(DomainModel):
    quantity: int


class ScopeGuard:
    async def can_activate(self, context):
        return context.request.headers.get("x-scope") == "yes"

    async def handle_rejection(self, context):
        return JSONResponse({"type": "urn:app:scope-required", "status": 403}, status_code=403)


@dataclass
class Open(DomainModel):
    opening_cash: str = "0"


@use_guards(ScopeGuard())
class GuardedController(Controller):
    @post("/guarded/adjust")
    async def adjust(self, body: Adjust) -> dict:
        return {"quantity": body.quantity}

    @post("/guarded/open")
    async def open(self, body: Open) -> dict:
        return {"opening_cash": body.opening_cash}


@pytest.fixture if pytest_asyncio is None else pytest_asyncio.fixture
async def client(app):
    from quadkit.identity.di.provider import IdentityProvider
    from quadkit.observability.di.sub_providers.observability import ObservabilityProvider

    config = WebConfig(rate_limit=RateLimitConfig(enabled=False), security=SecurityConfig(csrf=CSRFConfig(enabled=False)))
    env = TestEnvironment(app)
    env.use_provider(IdentityProvider())
    env.use_provider(ObservabilityProvider())
    env.use_provider(WebProvider(web_config=config, controllers=[GuardedController]))
    async with env.context():
        starlette_app = env.get_provider("web").starlette
        async with AsyncClient(transport=ASGITransport(app=starlette_app), base_url="http://test") as c:
            yield c


@pytest.mark.asyncio
async def test_the_guard_answers_before_the_body_is_validated(client):
    response = await client.post("/guarded/adjust", json={"quantity": "not a number"})
    assert response.status_code == 403
    assert response.json()["type"] == "urn:app:scope-required"


@pytest.mark.asyncio
async def test_with_scope_the_body_is_validated_and_the_handler_runs(client):
    bad = await client.post("/guarded/adjust", json={"quantity": "not a number"}, headers={"x-scope": "yes"})
    assert bad.status_code == 422
    assert bad.json()["errors"][0]["field"].endswith("quantity")

    ok = await client.post("/guarded/adjust", json={"quantity": 3}, headers={"x-scope": "yes"})
    assert ok.status_code == 200
    assert ok.json() == {"quantity": 3}


@pytest.mark.asyncio
async def test_field_paths_name_the_json_field_not_the_handler_parameter(client):
    """``body.quantity`` told the client about a Python parameter; ``quantity`` is what it sent."""
    bad = await client.post("/guarded/adjust", json={}, headers={"x-scope": "yes"})
    assert bad.status_code == 422
    (error,) = bad.json()["errors"]
    assert error["field"] == "quantity"
    assert error["code"] == "missing"


def test_one_unresolvable_annotation_does_not_untype_the_others():
    """``request: Request`` under TYPE_CHECKING must not turn the body DTO into "assumed DI"."""
    from quadkit.web.routing.param_coercion import _cached_get_type_hints_for_handler

    source = (
        "from __future__ import annotations\n"
        "from typing import TYPE_CHECKING\n"
        "from dataclasses import dataclass\n"
        "from quadkit.domain import DomainModel\n"
        "if TYPE_CHECKING:\n"
        "    from starlette.requests import Request\n"
        "@dataclass\n"
        "class Body(DomainModel):\n"
        "    n: int\n"
        "async def handler(item_id: int, request: Request, body: Body) -> dict: ...\n"
    )
    import sys
    import types

    module = types.ModuleType("test_module_for_hints")
    sys.modules[module.__name__] = module
    try:
        exec(compile(source, "<hints>", "exec"), module.__dict__)  # noqa: S102 — building a module with a TYPE_CHECKING-only name
        hints = _cached_get_type_hints_for_handler(module.handler)
    finally:
        sys.modules.pop(module.__name__, None)
    assert hints["item_id"] is int
    assert hints["body"] is module.Body
    assert hints["request"] == "Request", "the one name that cannot be resolved stays a string"


@pytest.mark.asyncio
async def test_an_empty_body_binds_a_dto_whose_fields_all_default(client):
    """``POST /open`` with no body is a till with no float, not a malformed request."""
    response = await client.post("/guarded/open", headers={"x-scope": "yes"})
    assert response.status_code == 200, response.text
    assert response.json() == {"opening_cash": "0"}


@pytest.mark.asyncio
async def test_an_empty_body_against_required_fields_names_the_fields(client):
    response = await client.post("/guarded/adjust", headers={"x-scope": "yes"})
    assert response.status_code == 422
    assert [e["field"] for e in response.json()["errors"]] == ["quantity"]
