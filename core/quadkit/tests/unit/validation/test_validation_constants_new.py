"""Tests for validation constants."""

from __future__ import annotations

from quadkit.validation.constants import (
    CODE_CUSTOM,
    CODE_EMAIL,
    CODE_MAX_LENGTH,
    CODE_MIN_LENGTH,
    CODE_ONE_OF,
    CODE_PATTERN,
    CODE_RANGE,
    CODE_RANGE_MAX,
    CODE_RANGE_MIN,
    CODE_REQUIRED,
    CODE_TYPE,
)


class TestValidationCodes:
    """Tests for validation error codes."""

    def test_code_required(self) -> None:
        assert CODE_REQUIRED == "required"

    def test_code_min_length(self) -> None:
        assert CODE_MIN_LENGTH == "min_length"

    def test_code_max_length(self) -> None:
        assert CODE_MAX_LENGTH == "max_length"

    def test_code_pattern(self) -> None:
        assert CODE_PATTERN == "pattern"

    def test_code_range(self) -> None:
        assert CODE_RANGE == "range"

    def test_code_range_min(self) -> None:
        assert CODE_RANGE_MIN == "range_min"

    def test_code_range_max(self) -> None:
        assert CODE_RANGE_MAX == "range_max"

    def test_code_one_of(self) -> None:
        assert CODE_ONE_OF == "one_of"

    def test_code_email(self) -> None:
        assert CODE_EMAIL == "email_format"

    def test_code_type(self) -> None:
        assert CODE_TYPE == "type"

    def test_code_custom(self) -> None:
        assert CODE_CUSTOM == "custom"

    def test_all_codes_are_strings(self) -> None:
        codes = [
            CODE_REQUIRED,
            CODE_MIN_LENGTH,
            CODE_MAX_LENGTH,
            CODE_PATTERN,
            CODE_RANGE,
            CODE_RANGE_MIN,
            CODE_RANGE_MAX,
            CODE_ONE_OF,
            CODE_EMAIL,
            CODE_TYPE,
            CODE_CUSTOM,
        ]
        for code in codes:
            assert isinstance(code, str)
