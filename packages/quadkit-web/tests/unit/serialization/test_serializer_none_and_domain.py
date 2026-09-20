"""Unit tests for ResponseSerializer.serialize() — None, dict, and list cases.

Tests the high-level ``ResponseSerializer`` orchestrator which converts raw
handler return values into Starlette ``Response`` objects.
"""

from __future__ import annotations

from quadkit import serialization as json
from unittest.mock import MagicMock

import pytest
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response

from quadkit.web.serialization.serializers import ResponseSerializer

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_request() -> MagicMock:
    """A mock Starlette request with a JSON Accept header (forces JSON path)."""
    req = MagicMock(spec=StarletteRequest)
    req.headers = MagicMock()
    req.headers.get = MagicMock(return_value="application/json")
    return req


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestResponseSerializerNoneAndDomain:
    @pytest.mark.asyncio
    async def test_none_returns_204_no_content(self, mock_request: MagicMock) -> None:
        """``None`` handler result must map to HTTP 204 with no body."""
        serializer = ResponseSerializer()
        response = await serializer.serialize(None, mock_request)

        assert response.status_code == 204
        # 204 responses must carry no body
        body = getattr(response, "body", b"")
        assert body == b"" or body is None

    @pytest.mark.asyncio
    async def test_dict_returns_200_json_response(self, mock_request: MagicMock) -> None:
        """A plain ``dict`` must produce HTTP 200 with JSON-encoded body."""
        payload = {"id": 42, "name": "Quadkit"}

        serializer = ResponseSerializer()
        response = await serializer.serialize(payload, mock_request)

        assert response.status_code == 200
        assert json.loads(response.body) == payload

    @pytest.mark.asyncio
    async def test_list_returns_200_json_response(self, mock_request: MagicMock) -> None:
        """A plain ``list`` must produce HTTP 200 with JSON-encoded body."""
        payload = [{"id": 1}, {"id": 2}]

        serializer = ResponseSerializer()
        response = await serializer.serialize(payload, mock_request)

        assert response.status_code == 200
        assert json.loads(response.body) == payload

    @pytest.mark.asyncio
    async def test_empty_dict_returns_200(self, mock_request: MagicMock) -> None:
        """An empty ``{}`` is still a valid 200 JSON response."""
        serializer = ResponseSerializer()
        response = await serializer.serialize({}, mock_request)

        assert response.status_code == 200
        assert json.loads(response.body) == {}

    @pytest.mark.asyncio
    async def test_explicit_response_object_is_passed_through(
        self, mock_request: MagicMock
    ) -> None:
        """When the handler already returns a ``Response``, it must not be re-wrapped."""
        original = Response(content=b"raw", status_code=201, media_type="text/plain")

        serializer = ResponseSerializer()
        response = await serializer.serialize(original, mock_request)

        assert response is original
        assert response.status_code == 201
