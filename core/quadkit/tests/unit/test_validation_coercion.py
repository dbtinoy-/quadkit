"""Tests for the validation coercion engine."""

from __future__ import annotations

import dataclasses
import datetime
from enum import Enum
from typing import Any, Union
from uuid import UUID

import pytest

from quadkit.validation import SecretStr
from quadkit.validation.engine.coercion import (
    BOOL_FALSE,
    BOOL_TRUE,
    coerce_field_value,
    coerce_str_to_bool,
    coerce_to_bool,
)

# ── Bool coercion ─────────────────────────────────────────────────────────


class TestBoolCoercion:
    @pytest.mark.parametrize("word", ["true", "True", " TRUE ", "yes", "on", "1", "t", "y"])
    def test_truthy_words(self, word: str) -> None:
        assert coerce_str_to_bool(word) is True

    @pytest.mark.parametrize("word", ["false", "no", "off", "0", "f", "n"])
    def test_falsy_words(self, word: str) -> None:
        assert coerce_str_to_bool(word) is False

    def test_unknown_word_raises(self) -> None:
        with pytest.raises(ValueError, match="Cannot coerce"):
            coerce_str_to_bool("maybe")

    def test_bool_sets(self) -> None:
        assert "true" in BOOL_TRUE
        assert "false" in BOOL_FALSE
        assert len(BOOL_TRUE) == 6
        assert len(BOOL_FALSE) == 6

    def test_coerce_to_bool_dispatch(self) -> None:
        assert coerce_to_bool("yes") is True
        assert coerce_to_bool("no") is False
        assert coerce_to_bool(1) is True
        assert coerce_to_bool(0) is False
        assert coerce_to_bool([]) is False
        assert coerce_to_bool([1]) is True


# ── coerce_field_value: scalars ───────────────────────────────────────────


class TestScalarCoercion:
    def test_none_passthrough(self) -> None:
        assert coerce_field_value("x", None, {"x": int}, None) is None

    def test_missing_hint_passthrough(self) -> None:
        assert coerce_field_value("x", "abc", {}, None) == "abc"

    def test_int_from_str(self) -> None:
        assert coerce_field_value("n", "42", {"n": int}, None) == 42

    def test_int_invalid_str_returns_original(self) -> None:
        assert coerce_field_value("n", "nope", {"n": int}, None) == "nope"

    def test_float_from_str(self) -> None:
        assert coerce_field_value("f", "3.5", {"f": float}, None) == 3.5

    def test_bool_from_str(self) -> None:
        assert coerce_field_value("b", "on", {"b": bool}, None) is True
        assert coerce_field_value("b", "off", {"b": bool}, None) is False

    def test_bool_from_int(self) -> None:
        assert coerce_field_value("b", 1, {"b": bool}, None) is True
        assert coerce_field_value("b", 0, {"b": bool}, None) is False

    def test_bool_bool_passthrough(self) -> None:
        assert coerce_field_value("b", True, {"b": bool}, None) is True

    def test_bool_invalid_str_raises(self) -> None:
        # Strict: uncoercible bool config values must fail loudly.
        with pytest.raises(ValueError, match="Cannot coerce"):
            coerce_field_value("b", "garbage", {"b": bool}, None)

    def test_uuid_from_str(self) -> None:
        uid = "123e4567-e89b-12d3-a456-426614174000"
        result = coerce_field_value("u", uid, {"u": UUID}, None)
        assert isinstance(result, UUID)
        assert str(result) == uid

    def test_uuid_invalid_returns_original(self) -> None:
        assert coerce_field_value("u", "not-a-uuid", {"u": UUID}, None) == "not-a-uuid"

    def test_id_field_uuid_heuristic(self) -> None:
        uid = "123e4567-e89b-12d3-a456-426614174000"
        result = coerce_field_value("id", uid, {"id": str}, None)
        assert isinstance(result, UUID)
        # Non-UUID id strings pass through
        assert coerce_field_value("id", "plain-id", {"id": str}, None) == "plain-id"

    def test_datetime_from_iso(self) -> None:
        stamp = coerce_field_value(
            "d", "2026-01-02T03:04:05", {"d": datetime.datetime}, None
        )
        assert isinstance(stamp, datetime.datetime)
        assert stamp.year == 2026

    def test_enum_from_str_and_int(self) -> None:
        class Color(Enum):
            RED = 1
            BLUE = "blue"

        assert coerce_field_value("c", 1, {"c": Color}, None) is Color.RED
        assert coerce_field_value("c", "blue", {"c": Color}, None) is Color.BLUE

    def test_secretstr_from_str(self) -> None:
        result = coerce_field_value("s", "hunter2", {"s": SecretStr}, None)
        assert isinstance(result, SecretStr)

    def test_optional_unwraps_to_first_non_none(self) -> None:
        # typing.Union form — exercises the __origin__-is-Union branch.
        # (Dict values are types, not annotations — UP007 does not apply.)
        hints: dict[str, Any] = {"n": Union[int, None]}  # noqa: UP007
        assert coerce_field_value("n", "5", hints, None) == 5
        assert coerce_field_value("n", None, hints, None) is None


class TestOptionalPipeSyntax:
    def test_pipe_union_int(self) -> None:
        hints: dict[str, Any] = {"n": int | None}
        assert coerce_field_value("n", "7", hints, None) == 7

    def test_pipe_union_str_field(self) -> None:
        hints: dict[str, Any] = {"s": str | None}
        assert coerce_field_value("s", "x", hints, None) == "x"


# ── coerce_field_value: models and collections ────────────────────────────


@dataclasses.dataclass
class InnerModel:
    value: int = 0

    @classmethod
    def model_validate(cls, data: dict[str, Any]) -> InnerModel:
        return cls(**data)


@dataclasses.dataclass
class OuterModel(InnerModel):
    extra: str = ""


def test_nested_model_from_dict() -> None:
    result = coerce_field_value("m", {"value": 3}, {"m": InnerModel}, None)
    assert isinstance(result, InnerModel)
    assert result.value == 3


def test_plain_dataclass_from_dict() -> None:
    @dataclasses.dataclass
    class Plain:
        a: int = 1
        b: str = ""

    result = coerce_field_value("p", {"a": 5, "b": "x"}, {"p": Plain}, None)
    assert isinstance(result, Plain)
    assert result.a == 5
    assert result.b == "x"


def test_list_of_models() -> None:
    hints = {"items": list[InnerModel]}
    result = coerce_field_value("items", [{"value": 1}, {"value": 2}], hints, None)
    assert [item.value for item in result] == [1, 2]


def test_list_of_models_non_dict_items_passthrough() -> None:
    hints = {"items": list[InnerModel]}
    existing = InnerModel(value=9)
    result = coerce_field_value("items", [existing], hints, None)
    assert result[0] is existing


def test_dict_of_models_scores_specificity() -> None:
    # OuterModel has more fields overlapping {"value", "extra"} than InnerModel.
    @classmethod
    def outer_validate(cls, data: dict[str, Any]) -> OuterModel:
        return cls(**data)

    OuterModel.model_validate = outer_validate  # type: ignore[method-assign]

    hints = {"m": dict[str, OuterModel]}
    result = coerce_field_value("m", {"k": {"value": 1, "extra": "e"}}, hints, None)
    assert isinstance(result["k"], OuterModel)
    assert result["k"].extra == "e"


def test_dict_union_value_types() -> None:
    hints = {"m": dict[str, InnerModel | OuterModel]}
    result = coerce_field_value("m", {"k": {"value": 7, "extra": "z"}}, hints, None)
    assert isinstance(result["k"], (InnerModel, OuterModel))
    assert result["k"].value == 7


def test_dict_without_model_types_passthrough() -> None:
    hints = {"m": dict[str, int]}
    data = {"k": 3}
    assert coerce_field_value("m", data, hints, None) == data


def test_non_dict_value_for_model_field_passthrough() -> None:
    result = coerce_field_value("m", "not a dict", {"m": InnerModel}, None)
    assert result == "not a dict"
