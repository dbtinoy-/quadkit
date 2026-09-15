"""Tests for security exceptions (Task 1 — core package creation).

Adapted from quadkit-security/tests/unit/test_exceptions.py.
"""

from __future__ import annotations

import pytest

from quadkit.contracts.security import SecretNotFoundError
from quadkit.security.exceptions import (
    MiddlewareGuardError,
    SecretAccessError,
    SecretError,
    SecurityError,
)


class TestSecurityError:
    """Tests for SecurityError."""

    def test_security_error(self) -> None:
        """Test SecurityError can be instantiated."""
        err = SecurityError("Security error")
        assert err.message == "Security error"


class TestSecretError:
    """Tests for SecretError."""

    def test_secret_error(self) -> None:
        """Test SecretError can be instantiated."""
        err = SecretError("Secret error")
        assert err.message == "Secret error"


class TestSecretNotFoundError:
    """Tests for SecretNotFoundError."""

    def test_secret_not_found_error(self) -> None:
        """Test SecretNotFoundError can be instantiated."""
        err = SecretNotFoundError("api-key")
        assert err.message == "Secret not found: api-key"


class TestSecretAccessError:
    """Tests for SecretAccessError."""

    def test_secret_access_error(self) -> None:
        """Test SecretAccessError can be instantiated."""
        err = SecretAccessError("Access denied")
        assert err.message == "Access denied"


class TestMiddlewareGuardError:
    """Tests for MiddlewareGuardError."""

    def test_guard_error(self) -> None:
        """Test MiddlewareGuardError can be instantiated."""
        err = MiddlewareGuardError("GuardProtocol failed")
        assert err.message == "GuardProtocol failed"
