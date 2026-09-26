"""Tests for quadkit.http.validation.primitives."""

from __future__ import annotations

import pytest

from quadkit.http.exceptions import HTTPClientError
from quadkit.http.validation.primitives import (
    validate_port,
    validate_positive_int,
    validate_timeout,
)


class TestValidatePort:
    """Tests for validate_port."""

    def test_valid_port(self) -> None:
        """Valid ports pass."""
        validate_port(80)
        validate_port(443)
        validate_port(8080)
        validate_port(65535)
        validate_port(1)

    def test_port_1(self) -> None:
        """Port 1 passes (minimum)."""
        validate_port(1)

    def test_port_65535(self) -> None:
        """Port 65535 passes (maximum)."""
        validate_port(65535)

    def test_port_0_raises(self) -> None:
        """Port 0 raises."""
        with pytest.raises(HTTPClientError, match="between 1 and 65535"):
            validate_port(0)

    def test_negative_port_raises(self) -> None:
        """Negative port raises."""
        with pytest.raises(HTTPClientError, match="between 1 and 65535"):
            validate_port(-1)

    def test_port_65536_raises(self) -> None:
        """Port 65536 raises (above max)."""
        with pytest.raises(HTTPClientError, match="between 1 and 65535"):
            validate_port(65536)

    def test_string_port_raises(self) -> None:
        """String port raises."""
        with pytest.raises(HTTPClientError, match="must be an integer"):
            validate_port("8080")  # type: ignore

    def test_float_port_raises(self) -> None:
        """Float port raises."""
        with pytest.raises(HTTPClientError, match="must be an integer"):
            validate_port(8080.0)  # type: ignore

    def test_none_port_raises(self) -> None:
        """None port raises."""
        with pytest.raises(HTTPClientError, match="must be an integer"):
            validate_port(None)  # type: ignore


class TestValidateTimeout:
    """Tests for validate_timeout."""

    def test_none_timeout(self) -> None:
        """None timeout passes."""
        validate_timeout(None)

    def test_valid_positive_float(self) -> None:
        """Positive float passes."""
        validate_timeout(5.0)
        validate_timeout(0.001)
        validate_timeout(3600.0)

    def test_valid_positive_int(self) -> None:
        """Positive int passes."""
        validate_timeout(30)
        validate_timeout(60)

    def test_zero_timeout_raises(self) -> None:
        """Zero timeout raises."""
        with pytest.raises(HTTPClientError, match="must be positive"):
            validate_timeout(0)

    def test_negative_timeout_raises(self) -> None:
        """Negative timeout raises."""
        with pytest.raises(HTTPClientError, match="must be positive"):
            validate_timeout(-1.0)

    def test_string_timeout_raises(self) -> None:
        """String timeout raises."""
        with pytest.raises(HTTPClientError, match="must be a number"):
            validate_timeout("30")  # type: ignore

    def test_very_small_positive(self) -> None:
        """Very small positive passes."""
        validate_timeout(0.0001)

    def test_very_large_positive(self) -> None:
        """Very large positive passes."""
        validate_timeout(86400.0)


class TestValidatePositiveInt:
    """Tests for validate_positive_int."""

    def test_valid_positive_int(self) -> None:
        """Positive int passes."""
        validate_positive_int(1)
        validate_positive_int(100)
        validate_positive_int(999999)

    def test_zero_raises(self) -> None:
        """Zero raises."""
        with pytest.raises(HTTPClientError, match="must be positive"):
            validate_positive_int(0)

    def test_negative_raises(self) -> None:
        """Negative raises."""
        with pytest.raises(HTTPClientError, match="must be positive"):
            validate_positive_int(-1)

    def test_string_raises(self) -> None:
        """String raises."""
        with pytest.raises(HTTPClientError, match="must be an integer"):
            validate_positive_int("100")  # type: ignore

    def test_float_raises(self) -> None:
        """Float raises."""
        with pytest.raises(HTTPClientError, match="must be an integer"):
            validate_positive_int(100.0)  # type: ignore

    def test_none_raises(self) -> None:
        """None raises."""
        with pytest.raises(HTTPClientError, match="must be an integer"):
            validate_positive_int(None)  # type: ignore

    def test_custom_field_name(self) -> None:
        """Custom field name appears in error."""
        with pytest.raises(HTTPClientError, match="max_retries"):
            validate_positive_int(0, field="max_retries")

    def test_default_field_name(self) -> None:
        """Default field name is 'value'."""
        with pytest.raises(HTTPClientError, match="value"):
            validate_positive_int(0)

    def test_large_positive_int(self) -> None:
        """Large positive int passes."""
        validate_positive_int(2_000_000_000)

    def test_one(self) -> None:
        """One passes."""
        validate_positive_int(1)