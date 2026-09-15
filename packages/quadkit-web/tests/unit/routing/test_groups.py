"""Tests for routing/groups.py — RouteGroup and group decorator."""

from __future__ import annotations

import pytest

from quadkit.web.routing.controllers import Controller
from quadkit.web.routing.groups import RouteGroup, group


class _BaseController(Controller):
    prefix = "/base"
    _guards: list = []
    _interceptors: list = []


class _PlainController(Controller):
    prefix = ""
    _guards: list = []
    _interceptors: list = []


class TestRouteGroupInit:
    def test_stores_prefix_and_controllers(self) -> None:
        rg = RouteGroup(prefix="/api", controllers=[_BaseController])
        assert rg.prefix == "/api"
        assert _BaseController in rg.controllers

    def test_defaults_to_empty_guards_interceptors_middleware(self) -> None:
        rg = RouteGroup(prefix="/api", controllers=[])
        assert rg.guards == []
        assert rg.interceptors == []
        assert rg.middleware == []

    def test_stores_custom_guards_interceptors(self) -> None:
        guard = object()
        interceptor = object()
        rg = RouteGroup(
            prefix="/api",
            controllers=[],
            guards=[guard],
            interceptors=[interceptor],
        )
        assert guard in rg.guards
        assert interceptor in rg.interceptors


class TestRouteGroupApplyGuards:
    def test_apply_guards_creates_subclass(self) -> None:
        guard = object()
        rg = RouteGroup(prefix="/api", controllers=[], guards=[guard])
        result = rg.apply_guards(_BaseController)
        assert issubclass(result, _BaseController)
        assert guard in result._guards

    def test_apply_guards_merges_with_existing_guards(self) -> None:
        existing_guard = object()
        new_guard = object()

        class ControllerWithGuard(Controller):
            prefix = "/x"
            _guards = [existing_guard]
            _interceptors: list = []

        rg = RouteGroup(prefix="/api", controllers=[], guards=[new_guard])
        result = rg.apply_guards(ControllerWithGuard)
        assert existing_guard in result._guards
        assert new_guard in result._guards

    def test_apply_guards_no_guards_keeps_existing(self) -> None:
        rg = RouteGroup(prefix="/api", controllers=[])
        result = rg.apply_guards(_BaseController)
        assert result._guards == []


class TestRouteGroupApplyInterceptors:
    def test_apply_interceptors_creates_subclass(self) -> None:
        interceptor = object()
        rg = RouteGroup(prefix="/api", controllers=[], interceptors=[interceptor])
        result = rg.apply_interceptors(_BaseController)
        assert issubclass(result, _BaseController)
        assert interceptor in result._interceptors

    def test_apply_interceptors_merges_with_existing(self) -> None:
        existing = object()
        new = object()

        class ControllerWithInterceptor(Controller):
            prefix = "/x"
            _guards: list = []
            _interceptors = [existing]

        rg = RouteGroup(prefix="/api", controllers=[], interceptors=[new])
        result = rg.apply_interceptors(ControllerWithInterceptor)
        assert existing in result._interceptors
        assert new in result._interceptors


class TestRouteGroupFinalize:
    def test_finalize_combines_prefix_with_existing(self) -> None:
        rg = RouteGroup(prefix="/api/v1", controllers=[_BaseController])
        results = rg.finalize()
        assert len(results) == 1
        combined = results[0]
        assert combined.prefix == "/api/v1/base"

    def test_finalize_uses_group_prefix_when_no_existing(self) -> None:
        rg = RouteGroup(prefix="/api", controllers=[_PlainController])
        results = rg.finalize()
        assert results[0].prefix == "/api"

    def test_finalize_applies_guards_and_interceptors(self) -> None:
        guard = object()
        interceptor = object()
        rg = RouteGroup(
            prefix="/api",
            controllers=[_BaseController],
            guards=[guard],
            interceptors=[interceptor],
        )
        results = rg.finalize()
        assert guard in results[0]._guards
        assert interceptor in results[0]._interceptors

    def test_finalize_multiple_controllers(self) -> None:
        rg = RouteGroup(prefix="/api", controllers=[_BaseController, _PlainController])
        results = rg.finalize()
        assert len(results) == 2


class TestGroupDecorator:
    def test_group_returns_route_group(self) -> None:
        decorator = group("/api/v1")
        result = decorator([_BaseController])
        assert isinstance(result, RouteGroup)

    def test_group_sets_prefix(self) -> None:
        result = group("/api/v2")([_BaseController])
        assert result.prefix == "/api/v2"

    def test_group_sets_guards(self) -> None:
        guard = object()
        result = group("/api", guards=[guard])([_BaseController])
        assert guard in result.guards

    def test_group_sets_interceptors(self) -> None:
        interceptor = object()
        result = group("/api", interceptors=[interceptor])([_BaseController])
        assert interceptor in result.interceptors

    def test_group_sets_middleware(self) -> None:
        mw = object()
        result = group("/api", middleware=[mw])([_BaseController])
        assert mw in result.middleware

    def test_group_defaults_empty_lists(self) -> None:
        result = group("/api")([])
        assert result.guards == []
        assert result.interceptors == []
        assert result.middleware == []
