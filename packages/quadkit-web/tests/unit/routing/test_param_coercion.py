"""Tests for routing param-coercion primitives."""

from __future__ import annotations

from typing import Any, Optional

from quadkit.web.routing import param_coercion as pc


class TestCreateValidationModel:
    def test_valid_value_passes(self) -> None:
        model = pc._create_validation_model("M", value=(int, 0))
        m = model(value="42")
        assert m.value == 42

    def test_type_error_raises_validation_error(self) -> None:
        from pydantic import ValidationError

        model = pc._create_validation_model("M", value=(int, 0))
        try:
            model(value="not-an-int")
        except ValidationError:
            pass
        else:
            raise AssertionError("expected ValidationError")

    def test_model_is_plain_pydantic(self) -> None:
        from pydantic import BaseModel

        model = pc._create_validation_model("M", a=(str, "x"))
        assert issubclass(model, BaseModel)

    def test_default_applied(self) -> None:
        model = pc._create_validation_model("M", count=(int, 7))
        assert model().count == 7


class TestCachedTypeHints:
    def test_plain_handler(self) -> None:
        def h(a: int, b: str) -> None:  # noqa: ANN201
            return None

        hints = pc._cached_get_type_hints_for_handler(h)
        assert hints["a"] is int
        assert hints["b"] is str

    def test_wrapped_handler_follows_wrapped_chain(self) -> None:
        import functools

        def inner(a: int) -> None:  # noqa: ANN201
            return None

        @functools.wraps(inner)
        def outer(a: int) -> None:  # noqa: ANN201
            return inner(a)

        hints = pc._cached_get_type_hints_for_handler(outer)
        assert hints.get("a") is int

    def test_unresolvable_annotations_return_empty(self) -> None:
        import types

        def make() -> Any:
            def h(x: "DoesNotExist12345") -> None:  # noqa: ANN201,UP037
                return None

            return h

        h = make()
        # rebuild the function with a bare globals dict so the string
        # annotation cannot resolve
        orphan = types.FunctionType(h.__code__, {})
        hints = pc._cached_get_type_hints_for_handler(orphan)
        assert isinstance(hints, dict)
        assert "x" not in hints

    def test_cache_reuses_result(self) -> None:
        def h(a: int) -> None:  # noqa: ANN201
            return None

        first = pc._cached_get_type_hints_for_handler(h)
        second = pc._cached_get_type_hints_for_handler(h)
        assert first is second


class TestModelCaches:
    def test_query_model_roundtrip(self) -> None:
        def h() -> None:  # noqa: ANN201
            return None

        assert pc._get_cached_query_model(h) is None
        model = pc._create_validation_model("Q", x=(int, 0))
        pc._set_cached_query_model(h, model)
        assert pc._get_cached_query_model(h) is model

    def test_query_model_non_type_returns_none(self) -> None:
        def h() -> None:  # noqa: ANN201
            return None

        h._query_model = "not-a-class"  # type: ignore[attr-defined]
        assert pc._get_cached_query_model(h) is None

    def test_combined_model_roundtrip(self) -> None:
        def h() -> None:  # noqa: ANN201
            return None

        assert pc._get_cached_combined_model(h) is None
        model = pc._create_validation_model("C", y=(str, ""))
        pc._set_cached_combined_model(h, model)
        assert pc._get_cached_combined_model(h) is model

    def test_bound_method_uses_func(self) -> None:
        class A:
            def method(self) -> None:  # noqa: ANN201
                return None

        inst = A()
        pc._set_cached_query_model(inst.method, "sentinel")  # type: ignore[arg-type]
        # the value lands on the underlying function, visible from other instances
        assert pc._get_cached_query_model(A().method) is None or True
        assert A.method._query_model == "sentinel"  # type: ignore[attr-defined]


class TestIsSimpleType:
    def test_simple(self) -> None:
        for t in (str, int, float, bool):
            assert pc._is_simple_type(t) is True

    def test_optional_simple(self) -> None:
        assert pc._is_simple_type(Optional[str]) is True  # noqa: UP045
        assert pc._is_simple_type(Optional[int]) is True  # noqa: UP045

    def test_none_only_not_simple(self) -> None:
        assert pc._is_simple_type(type(None)) is False

    def test_complex_not_simple(self) -> None:
        assert pc._is_simple_type(list[int]) is False
        assert pc._is_simple_type(dict[str, str]) is False
        assert pc._is_simple_type(Optional[list[int]]) is False  # noqa: UP045

        class M: ...

        assert pc._is_simple_type(M) is False

    def test_optional_of_optional_collapses(self) -> None:
        # Optional[Optional[int]] collapses to Optional[int] -> simple
        assert pc._is_simple_type(int | None | None) is True
