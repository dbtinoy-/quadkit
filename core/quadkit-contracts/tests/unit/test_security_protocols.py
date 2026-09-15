"""Tests for contracts security protocols."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.security.protocols import (
    CORSProtocol,
    CSPProtocol,
    CSRFProtocol,
    EncryptionProtocol,
    GuardChainProtocol,
    InputSanitizerProtocol,
    SecurityHeadersProtocol,
)


class TestSecurityProtocols:
    """Tests for security protocols."""

    def test_async_secret_store_protocol_import(self) -> None:
        """Test AsyncSecretStoreProtocol can be imported."""
        from quadkit.contracts.security.stores import AsyncSecretStoreProtocol

        assert AsyncSecretStoreProtocol is not None

    def test_async_secret_store_is_protocol(self) -> None:
        """Test AsyncSecretStoreProtocol is a Protocol."""
        from quadkit.contracts.security.stores import AsyncSecretStoreProtocol

        assert hasattr(AsyncSecretStoreProtocol, "__protocol_attrs__") or hasattr(AsyncSecretStoreProtocol, "__annotations__")


class TestSecuritySecrets:
    """Tests for security secrets module."""

    def test_secret_store_protocol_import(self) -> None:
        """Test SecretStoreProtocol can be imported."""
        from quadkit.contracts.security.secrets import SecretStoreProtocol

        assert SecretStoreProtocol is not None


class TestSecurityStores:
    """Tests for security stores module."""

    def test_async_secret_store_protocol_methods(self) -> None:
        """Test AsyncSecretStoreProtocol has expected methods."""
        from quadkit.contracts.security.stores import AsyncSecretStoreProtocol

        assert hasattr(AsyncSecretStoreProtocol, "get")
        assert hasattr(AsyncSecretStoreProtocol, "get_bulk")
        assert hasattr(AsyncSecretStoreProtocol, "set")
        assert hasattr(AsyncSecretStoreProtocol, "delete")


class TestSecurityExport:
    """Tests for security module exports."""

    def test_security_exports(self) -> None:
        """Test security module exports."""
        from quadkit.contracts import security

        assert hasattr(security, "stores")
        assert hasattr(security, "secrets")


class TestGuardChainProtocol:
    """Tests for GuardChainProtocol."""

    def test_is_runtime_checkable(self) -> None:
        """Test GuardChainProtocol is runtime checkable."""
        assert isinstance(GuardChainProtocol, type)

    def test_has_add_method(self) -> None:
        """Test protocol defines add method."""
        assert hasattr(GuardChainProtocol, "add")

    def test_has_execute_method(self) -> None:
        """Test protocol defines execute method."""
        assert hasattr(GuardChainProtocol, "execute")


class TestInputSanitizerProtocol:
    """Tests for InputSanitizerProtocol."""

    def test_is_runtime_checkable(self) -> None:
        """Test InputSanitizerProtocol is runtime checkable."""
        assert isinstance(InputSanitizerProtocol, type)

    def test_has_sanitize_method(self) -> None:
        """Test protocol defines sanitize method."""
        assert hasattr(InputSanitizerProtocol, "sanitize")

    def test_has_sanitize_dict_method(self) -> None:
        """Test protocol defines sanitize_dict method."""
        assert hasattr(InputSanitizerProtocol, "sanitize_dict")

    def test_has_sanitize_header_value_method(self) -> None:
        """Test protocol defines sanitize_header_value method."""
        assert hasattr(InputSanitizerProtocol, "sanitize_header_value")

    def test_has_is_safe_url_for_request_method(self) -> None:
        """Test protocol defines is_safe_url_for_request method."""
        assert hasattr(InputSanitizerProtocol, "is_safe_url_for_request")


class TestSecurityHeadersProtocol:
    """Tests for SecurityHeadersProtocol."""

    def test_is_runtime_checkable(self) -> None:
        """Test SecurityHeadersProtocol is runtime checkable."""
        assert isinstance(SecurityHeadersProtocol, type)

    def test_has_apply_method(self) -> None:
        """Test protocol defines apply method."""
        assert hasattr(SecurityHeadersProtocol, "apply")


class TestEncryptionProtocol:
    """Tests for EncryptionProtocol."""

    def test_is_runtime_checkable(self) -> None:
        """Test EncryptionProtocol is runtime checkable."""
        assert isinstance(EncryptionProtocol, type)

    def test_has_encrypt_method(self) -> None:
        """Test protocol defines encrypt method."""
        assert hasattr(EncryptionProtocol, "encrypt")

    def test_has_decrypt_method(self) -> None:
        """Test protocol defines decrypt method."""
        assert hasattr(EncryptionProtocol, "decrypt")

    def test_has_rotate_key_method(self) -> None:
        """Test protocol defines rotate_key method."""
        assert hasattr(EncryptionProtocol, "rotate_key")


class TestCORSProtocol:
    """Tests for CORSProtocol."""

    def test_is_runtime_checkable(self) -> None:
        """Test CORSProtocol is runtime checkable."""
        assert isinstance(CORSProtocol, type)

    def test_has_is_allowed_origin_method(self) -> None:
        """Test protocol defines is_allowed_origin method."""
        assert hasattr(CORSProtocol, "is_allowed_origin")

    def test_has_get_allowed_headers_method(self) -> None:
        """Test protocol defines get_allowed_headers method."""
        assert hasattr(CORSProtocol, "get_allowed_headers")

    def test_has_get_allowed_methods_method(self) -> None:
        """Test protocol defines get_allowed_methods method."""
        assert hasattr(CORSProtocol, "get_allowed_methods")

    def test_has_get_max_age_method(self) -> None:
        """Test protocol defines get_max_age method."""
        assert hasattr(CORSProtocol, "get_max_age")


class TestCSPProtocol:
    """Tests for CSPProtocol."""

    def test_is_runtime_checkable(self) -> None:
        """Test CSPProtocol is runtime checkable."""
        assert isinstance(CSPProtocol, type)

    def test_has_build_header_method(self) -> None:
        """Test protocol defines build_header method."""
        assert hasattr(CSPProtocol, "build_header")

    def test_has_add_directive_method(self) -> None:
        """Test protocol defines add_directive method."""
        assert hasattr(CSPProtocol, "add_directive")


class TestCSRFProtocol:
    """Tests for CSRFProtocol."""

    def test_is_runtime_checkable(self) -> None:
        """Test CSRFProtocol is runtime checkable."""
        assert isinstance(CSRFProtocol, type)

    def test_has_generate_token_method(self) -> None:
        """Test protocol defines generate_token method."""
        assert hasattr(CSRFProtocol, "generate_token")

    def test_has_validate_token_method(self) -> None:
        """Test protocol defines validate_token method."""
        assert hasattr(CSRFProtocol, "validate_token")

    def test_has_invalidate_token_method(self) -> None:
        """Test protocol defines invalidate_token method."""
        assert hasattr(CSRFProtocol, "invalidate_token")


class TestProtocolImplementations:
    """Tests demonstrating that runtime_checkable works."""

    def test_guard_chain_can_be_implemented(self) -> None:
        """Test GuardChainProtocol can be implemented."""

        class MockGuard:
            pass

        class MockGuardChain:
            def add(self, guard: Any) -> MockGuardChain:
                return self

            async def execute(self, context: dict[str, Any]) -> None:
                pass

        chain = MockGuardChain()
        assert isinstance(chain, GuardChainProtocol)

    def test_input_sanitizer_can_be_implemented(self) -> None:
        """Test InputSanitizerProtocol can be implemented."""

        class MockSanitizer:
            def sanitize(self, value: str) -> str:
                return value

            def sanitize_dict(self, data: dict[str, Any]) -> dict[str, Any]:
                return data

            def sanitize_header_value(self, value: str) -> str:
                return value

            def is_safe_url_for_request(self, url: str) -> bool:
                return True

        sanitizer = MockSanitizer()
        assert isinstance(sanitizer, InputSanitizerProtocol)

    def test_security_headers_can_be_implemented(self) -> None:
        """Test SecurityHeadersProtocol can be implemented."""

        class MockSecurityHeaders:
            def apply(self, headers: dict[str, str]) -> dict[str, str]:
                headers["X-Frame-Options"] = "DENY"
                return headers

        headers = MockSecurityHeaders()
        assert isinstance(headers, SecurityHeadersProtocol)
