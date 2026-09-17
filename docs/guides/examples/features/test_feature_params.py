"""Feature tour: typed handler parameters and declarative pipes.

Handler signatures declare where values come from — `query`, `header`,
or an annotated `DomainModel` body — and pipes transform or validate them
before business code runs. Builtin pipes parse (`ParseIntPipe`,
`ParseUUIDPipe`); a custom pipe is one `transform` method — here
`ClampPageSize`.
"""

from dataclasses import dataclass
from typing import Any

import pytest

from quadkit import Application
from quadkit.testing import WebTestBed
from quadkit.domain import DomainModel
from quadkit.web import Controller, WebModule, get, header, post, query
from quadkit.web.config.top_level import SecurityConfig, WebConfig
from quadkit.web.pipes.builtin.parse import ParseIntPipe


class ClampPageSize:
    """Custom pipe: never serve more than 50 rows per page."""

    async def transform(self, value: Any, metadata: Any = None) -> int:
        size = int(value if value is not None else 50)
        return min(size, 50)


@dataclass
class ItemIn(DomainModel):
    name: str
    price: int


class CatalogController(Controller):
    @get("/items")
    async def items(
        self,
        page: int = query(1, pipes=[ParseIntPipe()]),
        size: int = query(20, pipes=[ParseIntPipe(), ClampPageSize()]),
    ) -> dict:
        return {"page": page, "size": size}

    @post("/items")
    async def create(self, item: ItemIn) -> dict:
        # A DomainModel-typed parameter binds the JSON body by annotation.
        return {"created": item.name, "price": item.price}

    @get("/echo-request")
    async def echo_request(
        self, request_id: str | None = header(None, alias="x-request-id")
    ) -> dict:
        return {"request_id": request_id}


def create_app() -> Application:
    app = Application()
    app.add_module(
        WebModule.configure(
            controllers=[CatalogController],
            # JSON API for machine clients: cookie-based CSRF does not apply.
            web_config=WebConfig(security=SecurityConfig(enable_csrf=False)),
        )
    )
    return app


@pytest.mark.asyncio
async def test_query_pipes_parse_and_clamp() -> None:
    async with WebTestBed(create_app()) as bed:
        plain = bed.get("/items")
        assert plain.json == {"page": 1, "size": 20}

        parsed = bed.get("/items?page=3&size=200")
        assert parsed.json == {"page": 3, "size": 50}  # ParseInt + custom clamp


@pytest.mark.asyncio
async def test_body_maps_json_to_dataclass() -> None:
    async with WebTestBed(create_app()) as bed:
        created = bed.post("/items", json={"name": "desk lamp", "price": 4990})
        assert created.status_code == 200
        assert created.json == {"created": "desk lamp", "price": 4990}


@pytest.mark.asyncio
async def test_header_injection_with_alias() -> None:
    async with WebTestBed(create_app()) as bed:
        echoed = bed.get("/echo-request", headers={"x-request-id": "req-123"})
        assert echoed.json == {"request_id": "req-123"}

        absent = bed.get("/echo-request")
        assert absent.json == {"request_id": None}
