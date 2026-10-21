"""Contract tests for the DI response factory (responses/adapter.py).

Pins the WS-2 alignment decision: the framework's response factory builds the
quadkit response family (``FastJSONResponse``/``HTMLResponse``/...
— starlette subclasses), so payloads serialize through
``quadkit.serialization`` instead of starlette's stdlib encoder. The
observable gain: datetime/UUID payloads that starlette's ``JSONResponse``
would 500 on now render as ISO strings.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

from starlette.responses import Response as StarletteResponse

from quadkit.web.responses.adapter import StarletteResponseAdapter


def test_factory_json_serializes_datetime_and_uuid_natively() -> None:
    """Datetime/UUID payload -> 200 + ISO strings, no TypeError on render."""
    when = datetime(2026, 10, 18, 9, 30, tzinfo=UTC)
    ident = uuid4()

    response = StarletteResponseAdapter().json(content={"when": when, "id": ident})

    # still the starlette-compatible surface the protocol promises
    assert isinstance(response, StarletteResponse)
    assert response.status_code == 200

    body = json.loads(bytes(response.body))
    assert body["when"] == "2026-10-18T09:30:00+00:00"
    assert body["id"] == str(UUID(str(ident)))


def test_factory_html_and_redirect_keep_starlette_compatible_shapes() -> None:
    factory = StarletteResponseAdapter()

    html = factory.html("<h1>hello</h1>", status_code=201)
    assert isinstance(html, StarletteResponse)
    assert html.status_code == 201
    assert b"hello" in html.body

    redirect = factory.redirect("/there")
    assert isinstance(redirect, StarletteResponse)
    assert redirect.status_code == 302
    assert redirect.headers["location"] == "/there"
