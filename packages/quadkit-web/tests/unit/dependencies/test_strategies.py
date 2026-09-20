"""Tests for dependencies/strategies.py — WebParameterStrategy."""

from __future__ import annotations

import pytest

from quadkit.web.dependencies.strategies import WebParameterStrategy


class TestWebParameterStrategyInit:
    def test_defaults_empty(self) -> None:
        strategy = WebParameterStrategy()
        assert strategy._path == {}
        assert strategy._query == {}
        assert strategy._headers == {}
        assert strategy._request is None

    def test_with_all_params(self) -> None:
        req = object()
        strategy = WebParameterStrategy(
            path_params={"id": "42"},
            query_params={"q": "search"},
            headers={"x-api-key": "secret"},
            request=req,
        )
        assert strategy._path == {"id": "42"}
        assert strategy._query == {"q": "search"}
        assert strategy._headers == {"x-api-key": "secret"}
        assert strategy._request is req


class TestWebParameterStrategyResolve:
    @pytest.mark.asyncio
    async def test_resolves_path_param_with_type_conversion(self) -> None:
        strategy = WebParameterStrategy(path_params={"id": "42"})
        found, value = await strategy.resolve("id", int, None)
        assert found is True
        assert value == 42

    @pytest.mark.asyncio
    async def test_resolves_path_param_keeps_raw_on_type_error(self) -> None:
        strategy = WebParameterStrategy(path_params={"name": "john"})
        found, value = await strategy.resolve("name", int, None)
        assert found is True
        assert value == "john"

    @pytest.mark.asyncio
    async def test_resolves_query_param_single(self) -> None:
        strategy = WebParameterStrategy(query_params={"limit": "20"})
        found, value = await strategy.resolve("limit", int, None)
        assert found is True
        assert value == 20

    @pytest.mark.asyncio
    async def test_resolves_query_param_list(self) -> None:
        strategy = WebParameterStrategy(query_params={"ids": ["1", "2", "3"]})
        found, value = await strategy.resolve("ids", int, None)
        assert found is True
        assert value == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_resolves_query_param_list_keeps_raw_on_error(self) -> None:
        strategy = WebParameterStrategy(query_params={"tags": ["a", "b"]})
        found, value = await strategy.resolve("tags", int, None)
        assert found is True
        assert value == ["a", "b"]

    @pytest.mark.asyncio
    async def test_resolves_query_param_single_keeps_raw_on_error(self) -> None:
        strategy = WebParameterStrategy(query_params={"name": "alice"})
        found, value = await strategy.resolve("name", int, None)
        assert found is True
        assert value == "alice"

    @pytest.mark.asyncio
    async def test_resolves_header_case_insensitive(self) -> None:
        strategy = WebParameterStrategy(headers={"x-api-key": "secret"})
        # "x_api_key" → "x-api-key" after replace
        found, value = await strategy.resolve("x_api_key", str, None)
        assert found is True
        assert value == "secret"

    @pytest.mark.asyncio
    async def test_resolves_request_object_by_type(self) -> None:
        class FakeRequest:
            pass

        req = FakeRequest()
        strategy = WebParameterStrategy(request=req)
        found, value = await strategy.resolve("request", FakeRequest, None)
        assert found is True
        assert value is req

    @pytest.mark.asyncio
    async def test_resolves_request_by_class_name_match(self) -> None:
        class Request:
            pass

        req = Request()
        strategy = WebParameterStrategy(request=req)

        class Request:  # Same name, different class — matches by __name__
            pass

        found, value = await strategy.resolve("r", Request, None)
        assert found is True
        assert value is req

    @pytest.mark.asyncio
    async def test_not_found_returns_false_none(self) -> None:
        strategy = WebParameterStrategy()
        found, value = await strategy.resolve("unknown", str, None)
        assert found is False
        assert value is None

    @pytest.mark.asyncio
    async def test_path_param_takes_priority_over_query(self) -> None:
        strategy = WebParameterStrategy(
            path_params={"id": "path_val"},
            query_params={"id": "query_val"},
        )
        found, value = await strategy.resolve("id", str, None)
        assert found is True
        assert value == "path_val"

    @pytest.mark.asyncio
    async def test_request_not_resolved_when_type_differs(self) -> None:
        class FakeRequest:
            pass

        class OtherType:
            pass

        req = FakeRequest()
        strategy = WebParameterStrategy(request=req)
        found, value = await strategy.resolve("param", OtherType, None)
        assert found is False
