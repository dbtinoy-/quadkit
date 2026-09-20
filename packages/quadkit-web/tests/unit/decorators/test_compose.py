"""Tests for decorator composition utilities."""
from __future__ import annotations

import pytest

from quadkit.web.decorators import api_controller, compose, merge_metadata


class TestCompose:
    """Tests for the compose() utility."""

    def test_compose_single_decorator(self) -> None:
        def add_x(fn):
            fn.marked = "x"
            return fn

        @compose(add_x)
        def my_func():
            pass

        assert my_func.marked == "x"

    def test_compose_applies_outer_decorator_last(self) -> None:
        """Last decorator in the list wraps outermost; first wraps innermost."""
        call_order: list[str] = []

        def mark_a(fn):
            call_order.append("a")
            return fn

        def mark_b(fn):
            call_order.append("b")
            return fn

        @compose(mark_a, mark_b)
        def my_func():
            pass

        # reversed application: mark_b applied first, then mark_a
        assert call_order == ["b", "a"]

    def test_compose_result_is_callable(self) -> None:
        composed = compose()

        def fn():
            return 42

        result = composed(fn)
        assert callable(result)
        assert result() == 42

    def test_compose_with_no_decorators_identity(self) -> None:
        def fn():
            return "hello"

        wrapped = compose()(fn)
        assert wrapped() == "hello"


class TestApiController:
    """Tests for the api_controller() class decorator."""

    def test_sets_prefix(self) -> None:
        @api_controller(prefix="/api/v1")
        class MyController:
            pass

        assert MyController._controller_config["prefix"] == "/api/v1"

    def test_sets_guards(self) -> None:
        class MyGuard:
            pass

        @api_controller(guards=[MyGuard])
        class MyController:
            pass

        assert MyController._controller_config["guards"] == [MyGuard]

    def test_sets_interceptors(self) -> None:
        class MyInterceptor:
            pass

        @api_controller(interceptors=[MyInterceptor])
        class MyController:
            pass

        assert MyController._controller_config["interceptors"] == [MyInterceptor]

    def test_sets_version(self) -> None:
        @api_controller(version="2")
        class MyController:
            pass

        assert MyController._controller_config["version"] == "2"

    def test_defaults_when_no_args(self) -> None:
        @api_controller()
        class MyController:
            pass

        config = MyController._controller_config
        assert config["prefix"] == ""
        assert config["guards"] == []
        assert config["interceptors"] == []
        assert config["middleware"] == []
        assert config["version"] is None

    def test_returns_same_class(self) -> None:
        @api_controller()
        class MyController:
            pass

        assert isinstance(MyController, type)

    def test_preserves_existing_controller_config(self) -> None:
        class MyController:
            _controller_config = {"existing": True}

        api_controller(prefix="/new")(MyController)
        assert MyController._controller_config["existing"] is True
        assert MyController._controller_config["prefix"] == "/new"


class TestMergeMetadata:
    """Tests for merge_metadata()."""

    def test_merges_two_dicts(self) -> None:
        a = {"x": 1}
        b = {"y": 2}
        result = merge_metadata(a, b)
        assert result["x"] == 1
        assert result["y"] == 2

    def test_last_wins_by_default(self) -> None:
        """Default priority='last' means later dicts override earlier ones."""
        a = {"x": 1}
        b = {"x": 99}
        result = merge_metadata(a, b)
        assert result["x"] == 99

    def test_first_wins_when_priority_first(self) -> None:
        a = {"x": 1}
        b = {"x": 99}
        result = merge_metadata(a, b, priority="first")
        # priority="first": existing keys are not overridden
        assert result["x"] == 1

    def test_empty_dicts(self) -> None:
        result = merge_metadata({}, {})
        assert result == {}
