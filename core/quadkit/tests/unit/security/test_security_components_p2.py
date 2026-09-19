"""Unit tests for core security components (Task 2 subset).

Derived from quadkit-security/tests/unit/test_security_components.py.
Covers only transport-agnostic components: GuardChainImpl, use_guards,
EncryptionService, InputSanitizer.

HTTP-only tests (SecurityModule, CORSConfig, CORSMiddlewareFactory,
CSRFProtection) are intentionally excluded — those belong in quadkit-web
tests.
"""

from __future__ import annotations

import importlib.util

import pytest
from unittest.mock import AsyncMock

from quadkit.security.guards.chain import GuardChainImpl
from quadkit.security.guards.decorator import use_guards
from quadkit.security.encryption.service import EncryptionService
from quadkit.security.sanitization.sanitizer import InputSanitizer


# ---------------------------------------------------------------------------
# Origin guards
# ---------------------------------------------------------------------------


class TestCoreComponentsAreInCorePackage:
    """Verify all moved modules resolve to quadkit core, not quadkit-security."""

    def test_encryption_service_module_is_core(self) -> None:
        spec = importlib.util.find_spec("quadkit.security.encryption.service")
        assert spec is not None
        assert spec.origin is not None
        assert "quadkit-security" not in spec.origin, spec.origin

    def test_guards_chain_module_is_core(self) -> None:
        spec = importlib.util.find_spec("quadkit.security.guards.chain")
        assert spec is not None
        assert "quadkit-security" not in (spec.origin or "")

    def test_sanitization_sanitizer_module_is_core(self) -> None:
        spec = importlib.util.find_spec("quadkit.security.sanitization.sanitizer")
        assert spec is not None
        assert "quadkit-security" not in (spec.origin or "")


# ---------------------------------------------------------------------------
# GuardChainImpl
# ---------------------------------------------------------------------------


class TestGuardChainComponents:
    """Test GuardChainImpl functionality."""

    def test_guard_chain_creation(self) -> None:
        chain = GuardChainImpl()
        assert chain is not None

    def test_guard_chain_add(self) -> None:
        chain = GuardChainImpl()
        guard_fn = AsyncMock()
        guard_fn.can_activate = AsyncMock(return_value=True)
        chain = chain.add(guard_fn)
        assert len(chain._guards) == 1

    @pytest.mark.asyncio
    async def test_guard_chain_execute_all_pass(self) -> None:
        guard_fn = AsyncMock()
        guard_fn.can_activate = AsyncMock(return_value=True)
        chain = GuardChainImpl().add(guard_fn)
        result = await chain.execute({})
        assert result is True

    @pytest.mark.asyncio
    async def test_guard_chain_execute_one_fails(self) -> None:
        guard_fn = AsyncMock()
        guard_fn.can_activate = AsyncMock(return_value=False)
        chain = GuardChainImpl().add(guard_fn)
        result = await chain.execute({})
        assert result is False


# ---------------------------------------------------------------------------
# use_guards
# ---------------------------------------------------------------------------


class TestGuardDecorator:
    """Test guard decorator."""

    def test_guard_decorator_exists(self) -> None:
        assert use_guards is not None

    @pytest.mark.asyncio
    async def test_guard_decorator_basic(self) -> None:
        @use_guards()
        async def check_permission() -> bool:
            return True

        result = await check_permission()
        assert result is True


# ---------------------------------------------------------------------------
# EncryptionService
# ---------------------------------------------------------------------------


class TestEncryptionService:
    """Test EncryptionService functionality."""

    @pytest.fixture
    def encryption_service(self) -> EncryptionService:
        return EncryptionService(secret_key="test-secret-key-32-bytes!!")

    def test_service_creation(self, encryption_service: EncryptionService) -> None:
        assert encryption_service is not None

    def test_service_has_encrypt_method(
        self, encryption_service: EncryptionService
    ) -> None:
        assert hasattr(encryption_service, "encrypt")

    def test_service_has_decrypt_method(
        self, encryption_service: EncryptionService
    ) -> None:
        assert hasattr(encryption_service, "decrypt")

    def test_encrypt_decrypt_roundtrip(
        self, encryption_service: EncryptionService
    ) -> None:
        original = "secret message"
        encrypted = encryption_service.encrypt(original)
        decrypted = encryption_service.decrypt(encrypted)
        assert decrypted == original

    def test_encrypt_produces_different_ciphertext_each_time(
        self, encryption_service: EncryptionService
    ) -> None:
        """Each call to encrypt uses a fresh random nonce."""
        plaintext = "same input"
        ct1 = encryption_service.encrypt(plaintext)
        ct2 = encryption_service.encrypt(plaintext)
        assert ct1 != ct2

    def test_decrypt_wrong_key_raises(self) -> None:
        svc1 = EncryptionService(secret_key="key-one-exactly-32-chars-here!!")
        svc2 = EncryptionService(secret_key="key-two-exactly-32-chars-here!!")
        ciphertext = svc1.encrypt("hello")
        from quadkit.security.exceptions import DecryptionError

        with pytest.raises(DecryptionError):
            svc2.decrypt(ciphertext)


# ---------------------------------------------------------------------------
# InputSanitizer
# ---------------------------------------------------------------------------


class TestInputSanitizerComponents:
    """Test InputSanitizer functionality."""

    def test_sanitizer_creation(self) -> None:
        sanitizer = InputSanitizer()
        assert sanitizer is not None

    def test_sanitizer_has_sanitize_method(self) -> None:
        sanitizer = InputSanitizer()
        assert hasattr(sanitizer, "sanitize")

    def test_sanitize_removes_script(self) -> None:
        sanitizer = InputSanitizer()
        result = sanitizer.sanitize("<script>alert('xss')</script>")
        assert "<script>" not in result

    def test_sanitize_removes_onclick(self) -> None:
        sanitizer = InputSanitizer()
        result = sanitizer.sanitize('<button onclick="evil()">Click</button>')
        assert "onclick" not in result

    def test_sanitize_passes_through_safe_html(self) -> None:
        """In 'allow' mode (default), safe p tags pass through."""
        sanitizer = InputSanitizer()
        result = sanitizer.sanitize("<p>Hello</p>")
        assert "<p>Hello</p>" == result


# ---------------------------------------------------------------------------
# SecurityProvider (lightweight core variant)
# ---------------------------------------------------------------------------


class TestSecurityProvider:
    """Verify the core SecurityProvider is importable and has correct metadata."""

    def test_provider_is_importable(self) -> None:
        from quadkit.security.provider import SecurityProvider  # noqa: PLC0415

        assert SecurityProvider is not None

    def test_provider_name(self) -> None:
        from quadkit.security.provider import SecurityProvider  # noqa: PLC0415

        assert SecurityProvider.name == "security"

    def test_provider_priority_is_infrastructure(self) -> None:
        from quadkit.contracts.core import ProviderPriority  # noqa: PLC0415
        from quadkit.security.provider import SecurityProvider  # noqa: PLC0415

        assert SecurityProvider.priority == ProviderPriority.INFRASTRUCTURE
