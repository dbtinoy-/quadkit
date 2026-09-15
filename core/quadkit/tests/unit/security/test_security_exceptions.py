"""Unit tests for quadkit core security exceptions.

Adapted from quadkit-security/tests/unit/test_security_exceptions.py.
The critical addition is test_exceptions_module_is_core_package which
verifies that the module resolves to quadkit core, not quadkit-security.
That test fails before quadkit/src/quadkit/security/ exists and passes
once the core package is created (core's __path__ position takes priority).
"""

from __future__ import annotations

import importlib.util

from quadkit.contracts.exceptions import QuadkitError
from quadkit.contracts.exceptions.components import ComponentError
from quadkit.contracts.security import SecretNotFoundError
from quadkit.security.exceptions import (
    DecryptionError,
    EncryptionError,
    MiddlewareGuardError,
    SecretAccessError,
    SecretError,
    SecurityError,
)


class TestSecurityExceptionHierarchy:
    """Tests for security exception hierarchy."""

    def test_security_error_inherits_from_quadkit_error(self) -> None:
        assert issubclass(SecurityError, QuadkitError)

    def test_secret_error_inherits_from_security_error(self) -> None:
        assert issubclass(SecretError, SecurityError)

    def test_secret_not_found_error_inherits_from_component_error(self) -> None:
        assert issubclass(SecretNotFoundError, ComponentError)

    def test_secret_access_error_inherits_from_secret_error(self) -> None:
        assert issubclass(SecretAccessError, SecretError)

    def test_guard_error_inherits_from_quadkit_error(self) -> None:
        assert issubclass(MiddlewareGuardError, QuadkitError)

    def test_encryption_error_inherits_from_security_error(self) -> None:
        assert issubclass(EncryptionError, SecurityError)

    def test_decryption_error_inherits_from_security_error(self) -> None:
        assert issubclass(DecryptionError, SecurityError)


class TestSecurityError:
    """Tests for SecurityError."""

    def test_security_error_default_message(self) -> None:
        error = SecurityError()
        assert error.message is not None


class TestSecretError:
    """Tests for SecretError."""

    def test_secret_error_default_message(self) -> None:
        error = SecretError()
        assert error.message is not None


class TestSecretNotFoundError:
    """Tests for SecretNotFoundError."""

    def test_secret_not_found_error_inherits(self) -> None:
        assert issubclass(SecretNotFoundError, ComponentError)


class TestSecretAccessError:
    """Tests for SecretAccessError."""

    def test_secret_access_error_inherits(self) -> None:
        assert issubclass(SecretAccessError, SecretError)


class TestMiddlewareGuardError:
    """Tests for MiddlewareGuardError (from contracts)."""

    def test_guard_error_inherits(self) -> None:
        assert issubclass(MiddlewareGuardError, QuadkitError)

    def test_guard_error_default_message(self) -> None:
        error = MiddlewareGuardError()
        assert error.message is not None


class TestExceptionAllExports:
    """Tests to verify __all__ exports."""

    def test_all_contains_all_exceptions(self) -> None:
        from quadkit.security import exceptions as exc_module

        expected = [
            "DecryptionError",
            "EncryptionError",
            "MiddlewareGuardError",
            "SecretAccessError",
            "SecretError",
            "SecurityError",
        ]
        for item in expected:
            assert item in exc_module.__all__


class TestExceptionsModuleIsCore:
    """Verify the exceptions module resolves to quadkit core, not quadkit-security.

    This test is the TDD signal for Task 1: it fails while only
    quadkit-security exists, and passes once quadkit/src/quadkit/security/
    is created (core takes priority in quadkit.__path__).
    """

    def test_exceptions_module_is_core_package(self) -> None:
        spec = importlib.util.find_spec("quadkit.security.exceptions")
        assert spec is not None, "quadkit.security.exceptions must be importable"
        assert spec.origin is not None, "module must have a known origin path"
        assert "quadkit-security" not in spec.origin, (
            f"Expected quadkit.security.exceptions to resolve to quadkit core, "
            f"but it resolved to: {spec.origin!r}. "
            f"Create quadkit/src/quadkit/security/exceptions.py to fix this."
        )
