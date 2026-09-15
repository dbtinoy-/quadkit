"""Tests for domain module in quadkit core."""


import pytest
from quadkit.domain import constants, exceptions, types


class TestDomainConstants:
    """Tests for domain constants."""

    def test_env_prefix(self) -> None:
        """Test ENV_PREFIX constant exists."""
        assert hasattr(constants, "ENV_PREFIX")
        assert "QK" in constants.ENV_PREFIX


class TestDomainTypes:
    """Tests for domain types."""

    def test_domain_event_type(self) -> None:
        """Test DomainEventType exists."""
        assert hasattr(types, "DomainEventType")


class TestDomainExceptions:
    """Tests for domain exceptions."""

    def test_domain_error_exists(self) -> None:
        """Test DomainError exists."""
        from quadkit.domain.exceptions import DomainError

        error = DomainError("test")
        assert error is not None

    def test_domain_error_accepts_message(self) -> None:
        """Test DomainError accepts message."""
        from quadkit.domain.exceptions import DomainError

        error = DomainError("test message")
        assert "test message" in str(error)