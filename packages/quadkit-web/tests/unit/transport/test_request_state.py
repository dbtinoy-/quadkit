"""Test request state helpers."""

import pytest
from quadkit.web import HTTPError
from starlette.requests import Request

from quadkit.web.dependencies import (
    RequestState,
    get_current_user_optional,
    get_current_user_required,
    get_request_id,
)


class TestRequestState:
    """Test request state helpers."""

    def test_get_returns_value_if_exists(self):
        """Test get() returns value when it exists."""
        request = Request(scope={"type": "http"})
        request.state.user = {"id": 123}

        user = RequestState.get(request, "user", dict)
        assert user == {"id": 123}

    def test_get_returns_default_if_not_exists(self):
        """Test get() returns default when key doesn't exist."""
        request = Request(scope={"type": "http"})

        user = RequestState.get(request, "user", dict, default=None)
        assert user is None

    def test_require_raises_if_not_exists(self):
        """Test require() raises 500 if key doesn't exist."""
        request = Request(scope={"type": "http"})

        with pytest.raises(HTTPError) as exc_info:
            RequestState.require(request, "user")

        assert exc_info.value.status_code == 500

    def test_require_returns_value_if_exists(self):
        """Test require() returns value when it exists."""
        request = Request(scope={"type": "http"})
        request.state.user = {"id": 123}

        user = RequestState.require(request, "user")
        assert user == {"id": 123}

    def test_set_stores_value(self):
        """Test set() stores value in request state."""
        request = Request(scope={"type": "http"})

        RequestState.set(request, "test_key", "test_value")
        assert request.state.test_key == "test_value"

    @pytest.mark.asyncio
    async def test_get_current_user_optional_returns_none(self):
        """Test optional user dependency returns None."""
        request = Request(scope={"type": "http"})

        user = await get_current_user_optional(request)
        assert user is None

    @pytest.mark.asyncio
    async def test_get_current_user_optional_returns_user(self):
        """Test optional user dependency returns user when set."""
        request = Request(scope={"type": "http"})
        request.state.user = {"id": 123}

        user = await get_current_user_optional(request)
        assert user == {"id": 123}

    @pytest.mark.asyncio
    async def test_get_current_user_required_raises_401(self):
        """Test required user dependency raises 401."""
        request = Request(scope={"type": "http"})

        with pytest.raises(HTTPError) as exc_info:
            await get_current_user_required(request)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_required_returns_user(self):
        """Test required user dependency returns user when set."""
        request = Request(scope={"type": "http"})
        request.state.user = {"id": 456}

        user = await get_current_user_required(request)
        assert user == {"id": 456}

    @pytest.mark.asyncio
    async def test_get_request_id_returns_value(self):
        """Test get_request_id returns request ID when set."""
        request = Request(scope={"type": "http"})
        request.state.request_id = "req_abc123"

        request_id = await get_request_id(request)
        assert request_id == "req_abc123"

    @pytest.mark.asyncio
    async def test_get_request_id_raises_if_missing(self):
        request = Request({"type": "http"})
        with pytest.raises(HTTPError) as exc_info:
            await get_request_id(request)
        assert exc_info.value.status_code == 500
