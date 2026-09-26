"""Tests for auth module."""

from __future__ import annotations

import pytest

from quadkit.auth import AuthModule
from quadkit.auth.config import AuthConfig, JWTConfig
from quadkit.contracts.auth import (
    AuthenticatorProtocol,
    AuthorizerProtocol,
    TokenManagerProtocol,
)
from quadkit.di.module import DynamicModule


class TestAuthModule:
    """Test suite for AuthModule."""

    def test_module_decorator_exists(self) -> None:
        """Verify @module decorator is applied to AuthModule."""
        assert hasattr(AuthModule, '__quadkit_module__')

    def test_configure_with_none(self) -> None:
        """Verify configure() with None returns DynamicModule."""
        result = AuthModule.configure(None)
        assert isinstance(result, DynamicModule)
        assert result.module is AuthModule

    def test_configure_exports_authenticator(self) -> None:
        """Verify configure() exports AuthenticatorProtocol."""
        result = AuthModule.configure(None)
        assert AuthenticatorProtocol in result.exports

    def test_configure_exports_authorizer(self) -> None:
        """Verify configure() exports AuthorizerProtocol."""
        result = AuthModule.configure(None)
        assert AuthorizerProtocol in result.exports

    def test_configure_exports_token_manager(self) -> None:
        """Verify configure() exports TokenManagerProtocol."""
        result = AuthModule.configure(None)
        assert TokenManagerProtocol in result.exports

    def test_configure_with_dict_config(self) -> None:
        """Verify configure() accepts an AuthConfig instance with explicit settings."""
        config = AuthConfig(
            secret_key="test-secret-key-long-enough-for-tests",
            token=JWTConfig(secret_key="test-secret-key-long-enough-for-tests"),
        )
        result = AuthModule.configure(config)
        assert isinstance(result, DynamicModule)
        assert result.module is AuthModule
