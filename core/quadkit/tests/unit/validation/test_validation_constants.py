"""Tests for validation constants."""

import pytest
from quadkit.validation.constants import (
    CODE_REQUIRED,
    CODE_MIN_LENGTH,
    CODE_MAX_LENGTH,
    CODE_PATTERN,
    CODE_RANGE,
    CODE_ONE_OF,
    CODE_EMAIL,
    CODE_TYPE,
    CODE_CUSTOM,
)


class TestValidationConstants:
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

    def test_code_one_of(self) -> None:
        assert CODE_ONE_OF == "one_of"

    def test_code_email(self) -> None:
        assert CODE_EMAIL == "email_format"

    def test_code_type(self) -> None:
        assert CODE_TYPE == "type"

    def test_code_custom(self) -> None:
        assert CODE_CUSTOM == "custom"
