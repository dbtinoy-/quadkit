"""Unit tests for routing validation model building (no HTTP round-trip)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError
import pytest

from quadkit.web.routing.validation import (
    get_or_build_combined_model,
    get_or_build_query_model,
    validate_and_merge_request,
    validate_query_params,
)


class _UserBody(BaseModel):
    name: str
    age: int = 0


def _make_request(
    query: dict[str, str] | None = None,
    header_map: dict[str, str] | None = None,
    cookie_map: dict[str, str] | None = None,
    body: Any = None,
) -> Any:
    from starlette.datastructures import Headers, QueryParams

    q = QueryParams(query or {})
    h = Headers(header_map or {})
    c = cookie_map or {}

    class _Req:
        query_params = q
        headers = h
        cookies = c

        def json(self) -> Any:
            return body

    return _Req()


class TestQueryModel:
    def test_simple_types_collected(self) -> None:
        async def handler(q: str, limit: int = 10) -> None:
            return None

        model = get_or_build_query_model(handler)
        assert model is not None
        assert set(model.model_fields) == {"q", "limit"}

    def test_no_simple_types_returns_none(self) -> None:
        async def handler() -> None:
            return None

        assert get_or_build_query_model(handler) is None

    def test_body_models_excluded(self) -> None:
        async def handler(body: _UserBody) -> None:
            return None

        assert get_or_build_query_model(handler) is None

    def test_self_and_request_skipped(self) -> None:
        class Ctrl:
            async def h(self, q: str) -> None:
                return None

        model = get_or_build_query_model(Ctrl().h)
        assert set(model.model_fields) == {"q"}

    def test_caching(self) -> None:
        async def handler(q: str) -> None:
            return None

        assert get_or_build_query_model(handler) is get_or_build_query_model(handler)

    def test_validate_query_params_ok(self) -> None:
        async def handler(q: str, limit: int = 10) -> None:
            return None

        result = validate_query_params({"q": "x", "limit": "5"}, handler)
        assert result.q == "x"
        assert result.limit == 5

    def test_validate_query_params_empty_handler(self) -> None:
        async def handler() -> None:
            return None

        result = validate_query_params({}, handler)
        assert result is not None

    def test_validate_query_params_failure(self) -> None:
        async def handler(limit: int) -> None:
            return None

        with pytest.raises(PydanticValidationError):
            validate_query_params({"limit": "not-a-number"}, handler)


class TestCombinedModel:
    def test_mixed_sources(self) -> None:
        async def handler(q: str, body: _UserBody, svc: Any = None) -> None:
            return None

        model = get_or_build_combined_model(handler)
        assert model is not None
        # q is a field; body is a field; svc (DI-like, Any) is a field or skipped
        assert "q" in model.model_fields
        assert "body" in model.model_fields

    def test_no_fields_returns_none(self) -> None:
        async def handler() -> None:
            return None

        assert get_or_build_combined_model(handler) is None

    def test_caching(self) -> None:
        async def handler(q: str) -> None:
            return None

        m1 = get_or_build_combined_model(handler)
        assert m1 is get_or_build_combined_model(handler)


class TestValidateAndMergeRequest:
    async def test_no_fields_returns_none(self) -> None:
        async def handler() -> None:
            return None

        assert await validate_and_merge_request(_make_request(), handler, {}) is None

    async def test_merges_path_and_query(self) -> None:
        async def handler(uid: str, q: str) -> None:
            return None

        req = _make_request(query={"q": "search"})
        merged = await validate_and_merge_request(req, handler, {"uid": "42"})
        assert merged is not None
        assert merged.uid == "42"
        assert merged.q == "search"

    async def test_header_and_cookie_sources(self) -> None:
        from quadkit.web import cookie, header

        async def handler(x_app: str = header(alias="X-App"), sess: str = cookie(alias="sid")) -> None:
            return None

        req = _make_request(header_map={"X-App": "web"}, cookie_map={"sid": "abc"})
        merged = await validate_and_merge_request(req, handler, {})
        assert merged is not None
        assert merged.x_app == "web"
        assert merged.sess == "abc"

    async def test_validation_error_propagates(self) -> None:
        async def handler(count: int) -> None:
            return None

        req = _make_request(query={"count": "abc"})
        # the wrapper converts pydantic errors to the framework ValidationError
        from quadkit.contracts.exceptions.domain import (
            ValidationError as OriValidationError,
        )

        with pytest.raises(OriValidationError):
            await validate_and_merge_request(req, handler, {})
