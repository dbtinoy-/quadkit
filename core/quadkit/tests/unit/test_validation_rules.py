"""Tests for composable validation rules and Result-based helpers."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.contracts.exceptions.domain import FieldError
from quadkit.result import Err, Ok
from quadkit.validation.constants import (
    CODE_CUSTOM,
    CODE_EMAIL,
    CODE_MAX_LENGTH,
    CODE_MIN_LENGTH,
    CODE_ONE_OF,
    CODE_PATTERN,
    CODE_RANGE_MAX,
    CODE_RANGE_MIN,
    CODE_REQUIRED,
)
from quadkit.validation.rules.rules import (
    AbstractAsyncRule,
    AbstractRule,
    Custom,
    EmailFormat,
    MaxLength,
    MinLength,
    OneOf,
    Pattern,
    Range,
    Required,
    custom,
    email_format,
    max_length,
    min_length,
    one_of,
    pattern,
    range_check,
    required,
    validate_range,
    validate_required,
    validate_type,
)


def _err(result: Any) -> FieldError:
    assert result.is_err()
    return result.unwrap_err()


class TestRequired:
    def test_none_fails(self) -> None:
        err = _err(Required()("", "f") if False else Required()(None, "f"))
        assert err.field == "f"
        assert "required" in err.message.lower()

    def test_empty_and_blank_strings_fail(self) -> None:
        for value in ("", "   "):
            err = _err(Required()(value, "name"))
            assert err.code == CODE_REQUIRED

    def test_non_empty_passes_and_returns_value(self) -> None:
        assert required()("x", "f").unwrap() == "x"
        assert Required()(0, "f").unwrap() == 0  # 0 is a valid non-None value
        assert Required()([], "f").unwrap() == []


class TestMinMaxLength:
    def test_min_length(self) -> None:
        rule = min_length(3)
        assert _err(rule("ab", "s")).code == CODE_MIN_LENGTH
        assert rule("abc", "s").unwrap() == "abc"
        assert rule(None, "s").unwrap() is None  # None passes (optional)

    def test_max_length(self) -> None:
        rule = max_length(3)
        assert _err(rule("abcd", "s")).code == CODE_MAX_LENGTH
        assert rule("abc", "s").unwrap() == "abc"
        assert rule(None, "s").unwrap() is None


class TestPattern:
    def test_match_and_mismatch(self) -> None:
        rule = pattern(r"^[A-Z]{2,3}$")
        assert rule("AB", "code").unwrap() == "AB"
        err = _err(rule("abc", "code"))
        assert err.code == CODE_PATTERN
        assert rule(None, "code").unwrap() is None

    def test_non_string_values_coerced(self) -> None:
        rule = pattern(r"^\d+$")
        assert rule(123, "n").unwrap() == 123
        assert _err(rule("12x", "n")).code == CODE_PATTERN


class TestRange:
    def test_bounds(self) -> None:
        rule = range_check(1, 10)
        assert rule(1, "n").unwrap() == 1
        assert rule(10, "n").unwrap() == 10
        assert _err(rule(0, "n")).code == CODE_RANGE_MIN
        assert _err(rule(11, "n")).code == CODE_RANGE_MAX
        assert rule(None, "n").unwrap() is None

    def test_open_bounds(self) -> None:
        assert Range(min_val=5)(4, "n").is_err()
        assert Range(min_val=5)(5, "n").is_ok()
        assert Range(max_val=5)(6, "n").is_err()
        assert Range(max_val=5)(5, "n").is_ok()
        assert Range()(99, "n").is_ok()


class TestOneOf:
    def test_choices(self) -> None:
        rule = one_of("a", "b", "c")
        assert rule("b", "opt").unwrap() == "b"
        err = _err(rule("z", "opt"))
        assert err.code == CODE_ONE_OF
        assert "['a', 'b', 'c']" in err.message
        assert rule(None, "opt").unwrap() is None


class TestEmailFormat:
    def test_valid_emails(self) -> None:
        for email in (
            "user@example.com",
            "first.last+tag@sub.domain.org",
            "a_b%c-1@x.io",
        ):
            assert email_format()(email, "email").is_ok(), email

    def test_invalid_emails(self) -> None:
        for email in ("", "no-at-sign", "@no-local.com", "user@.com", "user@domain"):
            assert _err(email_format()(email, "email")).code == CODE_EMAIL

    def test_none_passes(self) -> None:
        assert email_format()(None, "email").unwrap() is None


class TestCustom:
    def test_predicate_pass_fail(self) -> None:
        rule = custom(lambda v: v > 10, "must be above 10")
        assert rule(11, "n").unwrap() == 11
        err = _err(rule(5, "n"))
        assert err.message == "must be above 10"
        assert err.code == CODE_CUSTOM
        assert rule(None, "n").unwrap() is None


class TestFactoriesReturnClasses:
    def test_factories(self) -> None:
        assert isinstance(required(), Required)
        assert isinstance(min_length(1), MinLength)
        assert isinstance(max_length(1), MaxLength)
        assert isinstance(pattern("x"), Pattern)
        assert isinstance(range_check(), Range)
        assert isinstance(one_of(1), OneOf)
        assert isinstance(email_format(), EmailFormat)
        assert isinstance(custom(bool, "m"), Custom)

    def test_abstract_rules_are_abstract(self) -> None:
        with pytest.raises(TypeError):
            AbstractRule()  # type: ignore[abstract]
        with pytest.raises(TypeError):
            AbstractAsyncRule()  # type: ignore[abstract]


class TestAsyncRules:
    async def test_async_rule_contract(self) -> None:
        class Unique(AbstractAsyncRule):
            async def __call__(self, value: Any, field_name: str) -> Any:
                if value in {"taken"}:
                    return Err(
                        FieldError(field=field_name, message="already taken", code="unique"),
                    )
                return Ok(value)

        rule = Unique()
        assert (await rule("free", "email")).unwrap() == "free"
        err = _err(await rule("taken", "email"))
        assert err.code == "unique"


# ── Result-based helpers ──────────────────────────────────────────────────


class TestHelperFunctions:
    def test_validate_required(self) -> None:
        assert validate_required(0, "count").unwrap() == 0
        result = validate_required(None, "count")
        assert result.is_err()
        assert "count is required" in str(result.unwrap_err())

    def test_validate_type(self) -> None:
        assert validate_type(5, int, "n").unwrap() == 5
        assert validate_type("5", int, "n").is_err()
        err = validate_type("5", int, "n").unwrap_err()
        assert "int" in str(err)

    def test_validate_range(self) -> None:
        assert validate_range(5, 1, 10, "n").unwrap() == 5
        assert validate_range(0, 1, 10, "n").is_err()
        assert "at least 1" in str(validate_range(0, 1, 10, "n").unwrap_err())
        assert validate_range(11, 1, 10, "n").is_err()
        assert "at most 10" in str(validate_range(11, 1, 10, "n").unwrap_err())
        assert validate_range(99, None, None, "n").unwrap() == 99
        assert validate_range(99, 1, None, "n").unwrap() == 99
