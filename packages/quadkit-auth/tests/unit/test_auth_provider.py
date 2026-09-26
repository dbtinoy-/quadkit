"""Unit tests for AuthBundleProvider."""

from __future__ import annotations

from collections.abc import Callable
from unittest.mock import MagicMock

import pytest

from quadkit.auth.authn.jwt import JWTTokenManager
from quadkit.auth.authn.password_hasher import ComposedPasswordHasher
from quadkit.auth.authn.security import PasswordHasher, PasswordPolicy
from quadkit.auth.authn.services import AuthenticationService
from quadkit.auth.authz.service import AuthorizationService
from quadkit.auth.di.bundle_provider import AuthBundleProvider
from quadkit.auth.di.sub_providers.authentication_provider import (
    AuthenticationProvider,
)
from quadkit.auth.di.sub_providers.google_oauth_provider import GoogleOAuthProvider
from quadkit.auth.session.manager import SessionManagerImpl
from quadkit.contracts.auth import (
    AuthenticatorProtocol,
    AuthorizerProtocol,
    AuthProviderProtocol,
    PasswordHasherProtocol,
    PasswordPolicyProtocol,
    TokenManagerProtocol,
)
from quadkit.contracts.core.provider import ProviderPriority
from quadkit.di.provider import Provider


class _HealthRegistry:
    def __init__(self) -> None:
        self.checks: dict[str, Callable[..., object]] = {}

    def add(self, name: str, callback: Callable[..., object]) -> None:
        self.checks[name] = callback


class _RecordingContainer:
    def __init__(self) -> None:
        self.bindings: dict[type, object] = {}

    def singleton(
        self, contract: type, implementation: object = None, **kwargs: object
    ) -> None:
        self.bindings[contract] = implementation or kwargs.get("factory")

    def transient(self, contract: type, implementation: type, **kwargs: object) -> None:
        self.bindings[contract] = implementation

    def has(self, service_type: type) -> bool:
        return service_type in self.bindings


class _BootContainer:
    async def resolve(self, contract: type) -> object:
        return MagicMock(spec=contract)

    async def resolve_optional(self, contract: type) -> object | None:
        _ = contract
        return None


class TestAuthBundleProviderStructure:
    """Test AuthBundleProvider class structure and attributes."""

    def test_provider_class_exists(self) -> None:
        """Verify AuthBundleProvider class exists and can be instantiated."""
        prov = AuthBundleProvider()
        assert prov is not None
        assert isinstance(prov, AuthBundleProvider)

    def test_provider_name(self) -> None:
        """Verify provider has correct name attribute."""
        prov = AuthBundleProvider()
        assert prov.name == "auth_bundle"

    def test_provider_priority(self) -> None:
        """Verify provider has SECURITY priority."""
        prov = AuthBundleProvider()
        assert prov.priority == ProviderPriority.SECURITY

    def test_provider_is_provider_subclass(self) -> None:
        """Verify AuthBundleProvider is a proper Provider subclass."""
        assert issubclass(AuthBundleProvider, Provider)

    def test_provider_has_required_methods(self) -> None:
        """Verify provider has all required lifecycle methods."""
        prov = AuthBundleProvider()
        assert hasattr(prov, "register")
        assert callable(prov.register)
        assert hasattr(prov, "boot")
        assert callable(prov.boot)
        assert hasattr(prov, "shutdown")
        assert callable(prov.shutdown)


class TestAuthBundleProviderLifecycle:
    """Test AuthBundleProvider lifecycle methods."""

    @staticmethod
    def _spy_provider(name: str, calls: list[str]) -> MagicMock:
        provider = MagicMock()

        async def _register(container: object) -> None:
            _ = container
            calls.append(f"{name}.register")

        async def _boot(container: object) -> None:
            _ = container
            calls.append(f"{name}.boot")

        async def _shutdown() -> None:
            calls.append(f"{name}.shutdown")

        provider.register.side_effect = _register
        provider.boot.side_effect = _boot
        provider.shutdown.side_effect = _shutdown
        return provider

    @pytest.mark.asyncio
    async def test_register_method_signature(self) -> None:
        """Verify register() method has correct async signature."""
        prov = AuthBundleProvider()
        container = _RecordingContainer()

        await prov.register(container)

    @pytest.mark.asyncio
    async def test_boot_method_signature(self) -> None:
        """Verify boot() method has correct async signature."""
        prov = AuthBundleProvider()
        reg_container = _RecordingContainer()
        await prov.register(reg_container)

        await prov.boot(_BootContainer())

    @pytest.mark.asyncio
    async def test_shutdown_method_signature(self) -> None:
        """Verify shutdown() method has correct async signature."""
        prov = AuthBundleProvider()

        await prov.shutdown()

    @pytest.mark.asyncio
    async def test_register_boot_shutdown_delegate_in_provider_order(self) -> None:
        """Lifecycle methods delegate to sub-providers in stable order."""
        calls: list[str] = []
        prov = AuthBundleProvider()
        prov._sub_providers = [
            self._spy_provider("authn", calls),
            self._spy_provider("token", calls),
            self._spy_provider("session", calls),
            self._spy_provider("authz", calls),
        ]

        container = MagicMock()

        await prov.register(container)
        await prov.boot(container)
        await prov.shutdown()

        assert calls == [
            "authn.register",
            "token.register",
            "session.register",
            "authz.register",
            "authn.boot",
            "token.boot",
            "session.boot",
            "authz.boot",
            "authz.shutdown",
            "session.shutdown",
            "token.shutdown",
            "authn.shutdown",
        ]

    @pytest.mark.asyncio
    async def test_register_binds_contracts_and_core_services(self) -> None:
        """Composite registration exposes protocol bindings at contract boundary."""
        prov = AuthBundleProvider()
        container = _RecordingContainer()

        await prov.register(container)

        assert PasswordPolicy in container.bindings
        assert AuthenticationService in container.bindings
        assert JWTTokenManager in container.bindings
        assert SessionManagerImpl in container.bindings
        assert AuthorizationService in container.bindings

        assert PasswordHasherProtocol in container.bindings
        assert isinstance(
            container.bindings[PasswordHasherProtocol],
            ComposedPasswordHasher,
        )
        assert PasswordHasher not in container.bindings
        assert PasswordPolicyProtocol in container.bindings
        assert AuthProviderProtocol in container.bindings
        assert AuthorizerProtocol in container.bindings

        # AuthModule.configure() exports AuthenticatorProtocol and
        # TokenManagerProtocol — both must actually be bound to container
        # keys, or every module that imports AuthModule and depends on
        # these protocols (rather than on AuthenticationService/
        # JWTTokenManager concrete types) would fail to resolve them.
        assert AuthenticatorProtocol in container.bindings
        assert TokenManagerProtocol in container.bindings

    @pytest.mark.asyncio
    async def test_authenticator_protocol_binding_is_usable(self) -> None:
        """The bound AuthenticatorProtocol implementation can authenticate.

        Regression test: previously nothing bound this key at all, so any
        code resolving ``AuthenticatorProtocol`` (rather than reaching into
        AuthMiddleware's private attributes) would fail with an unresolved
        dependency. Exercises the real composite end-to-end with an
        anonymous request (no credentials) to confirm it returns ``None``
        rather than raising.
        """
        prov = AuthBundleProvider()
        container = _RecordingContainer()
        await prov.register(container)

        authenticator = container.bindings[AuthenticatorProtocol]
        # Bound via factory=lambda: ...— resolve it like the DI container would.
        instance = authenticator() if callable(authenticator) else authenticator
        assert hasattr(instance, "authenticate")

        anonymous_request = MagicMock()
        anonymous_request.headers = {}
        anonymous_request.query_params = {}
        anonymous_request.cookies = {}
        result = await instance.authenticate(anonymous_request)
        assert result is None

    @pytest.mark.asyncio
    async def test_token_manager_protocol_binding_is_the_real_jwt_manager(
        self,
    ) -> None:
        """TokenManagerProtocol resolves to the same instance as JWTTokenManager.

        Regression test: previously only the concrete ``JWTTokenManager``
        type was bound; anything depending on the protocol instead would
        fail to resolve. Both keys must point at the identical instance so
        token state (keys, rotation) stays consistent regardless of which
        type a caller depends on.
        """
        prov = AuthBundleProvider()
        container = _RecordingContainer()
        await prov.register(container)

        token_manager_binding = container.bindings[JWTTokenManager]
        protocol_binding = container.bindings[TokenManagerProtocol]
        # Both are lambdas capturing the same self.token_manager instance.
        assert token_manager_binding() is protocol_binding()

    def test_google_oauth_provider_is_added_when_configured(self) -> None:
        """Google OAuth provider is auto-wired when Google config exists."""
        from quadkit.auth.config import AuthConfig, JWTConfig

        prov = AuthBundleProvider(
            config=AuthConfig(
                secret_key="bundle-secret-key",
                token=JWTConfig(secret_key="bundle-jwt-secret"),
                oauth2_providers={
                    "google": {
                        "client_id": "google-client-id",
                    },
                },
            ),
        )

        assert any(
            isinstance(sub_provider, GoogleOAuthProvider)
            for sub_provider in prov._sub_providers
        )


class TestAuthenticationProviderSecretGuard:
    def test_production_missing_secret_raises(self, monkeypatch) -> None:
        from quadkit.auth.config import AuthConfig, JWTConfig
        from quadkit.contracts.exceptions import ConfigurationError

        monkeypatch.setenv("QK_ENV", "development")
        config = AuthConfig(secret_key="dev-root-key", token=JWTConfig(secret_key=""))
        monkeypatch.setenv("QK_ENV", "production")
        with pytest.raises(ConfigurationError) as excinfo:
            AuthenticationProvider(config=config)
        assert "secret_key is required" in str(excinfo.value)

    def test_staging_missing_secret_raises(self, monkeypatch) -> None:
        from quadkit.auth.config import AuthConfig, JWTConfig
        from quadkit.contracts.exceptions import ConfigurationError

        monkeypatch.setenv("QK_ENV", "development")
        config = AuthConfig(secret_key="dev-root-key", token=JWTConfig(secret_key=""))
        monkeypatch.setenv("QK_ENV", "staging")
        with pytest.raises(ConfigurationError) as excinfo:
            AuthenticationProvider(config=config)
        assert "secret_key is required" in str(excinfo.value)

    def test_dev_missing_secret_falls_back_to_ephemeral(self, monkeypatch) -> None:
        from quadkit.auth.config import AuthConfig, JWTConfig

        monkeypatch.setenv("QK_ENV", "development")
        config = AuthConfig(secret_key="dev-root-key", token=JWTConfig(secret_key=""))
        provider = AuthenticationProvider(config=config)
        secret = provider.token_manager._key_store.keys["default"].get_secret_value()
        assert secret
        assert len(secret) >= 32
