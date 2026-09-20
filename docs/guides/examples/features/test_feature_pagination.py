"""Feature tour: pagination.

Offset style: declare `page`/`size` on the handler, return a
`Page(items, total, page, size)` — the framework binds the query string,
and the dataclass carries its derived `pages` count into the wire format.

Cursor style: return `cursor_page_to_response(CursorPage(...))` for the
standard `{"items": ..., "meta": {"next_cursor": ..., "has_more": ...}}`
envelope.

`paginated(...)` builds a strict query parser when raw control is wanted
(clamps, defaults, max size).
"""

import pytest
from starlette.requests import Request

from quadkit import Application
from quadkit.contracts.domain.pagination import CursorPage
from quadkit.testing import WebTestBed
from quadkit.web import Controller, WebModule, get
from quadkit.web.pagination import Page, cursor_page_to_response, paginated

DATA = [{"id": i, "name": f"user-{i:03d}"} for i in range(1, 102)]  # 101 rows


class UserController(Controller):
    prefix = "/users"

    @get("")
    async def list_users(self, request: Request, page: int = 1, size: int = 20) -> dict:
        start = (page - 1) * size
        return Page(
            items=DATA[start : start + size],
            total=len(DATA),
            page=page,
            size=size,
        )

    @get("/cursor")
    async def cursor_users(self, request: Request, cursor: str | None = None) -> dict:
        size = 3
        start = int(cursor) if cursor else 0
        window = DATA[start : start + size]
        next_id = start + size
        page_obj = CursorPage(
            items=window,
            next_cursor=str(next_id) if next_id < len(DATA) else None,
            prev_cursor=str(start) if start > 0 else None,
            has_more=next_id < len(DATA),
        )
        return cursor_page_to_response(page_obj)


def create_app() -> Application:
    app = Application()
    app.add_module(WebModule.configure(controllers=[UserController]))
    return app


@pytest.mark.asyncio
async def test_offset_pagination_binds_and_maths() -> None:
    async with WebTestBed(create_app()) as bed:
        page_two = bed.get("/users", params={"page": 2, "size": 10})
        assert page_two.status_code == 200
        body = page_two.json
        assert body["total"] == 101
        assert body["page"] == 2
        assert body["size"] == 10
        assert body["pages"] == 11  # 101 rows / 10 per page
        assert [row["id"] for row in body["items"]] == list(range(11, 21))

        # Defaults: first page of 20 without any params.
        first = bed.get("/users")
        assert [row["id"] for row in first.json["items"]] == list(range(1, 21))


@pytest.mark.asyncio
async def test_cursor_pagination_envelope() -> None:
    async with WebTestBed(create_app()) as bed:
        first = bed.get("/users/cursor")
        assert first.json == {
            "items": DATA[0:3],
            "meta": {"next_cursor": "3", "prev_cursor": None, "has_more": True},
        }

        second = bed.get("/users/cursor", params={"cursor": first.json["meta"]["next_cursor"]})
        assert second.json["items"] == DATA[3:6]
        assert second.json["meta"]["prev_cursor"] == "3"

        # Walk to the end — has_more flips and next_cursor goes None.
        end = bed.get("/users/cursor", params={"cursor": "99"})
        assert end.json["items"] == DATA[99:101]
        assert end.json["meta"]["has_more"] is False
        assert end.json["meta"]["next_cursor"] is None


def test_paginated_helper_clamps_and_defaults() -> None:
    parse = paginated(default_size=20, max_size=100)(lambda query: query)

    assert vars(parse({})) == {"page": 1, "size": 20, "sort_by": None, "sort_order": "asc"}
    clamped = parse({"page": "0", "size": "500"})
    assert clamped.page == 1
    assert clamped.size == 100  # clamped to max_size

    junk = parse({"page": "junk", "size": "junk"})
    assert junk.page == 1
    assert junk.size == 20  # falls back to defaults
