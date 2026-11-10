"""Authentication and authorization module for dependency injection."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.auth.authn.services import AuthenticationService
from quadkit.auth.storage.session_store import SessionStore
from quadkit.auth.storage.token_store import UserStoreProtocol
from quadkit.contracts.auth import (
    AuthenticatorProtocol,
    AuthorizerProtocol,
    TokenManagerProtocol,
)
from quadkit.contracts.auth.protocols import PasswordHasherProtocol
from quadkit.di.module import DynamicModule, Module, module

if TYPE_CHECKING:
    from quadkit.auth.config import UserStoreKind


@module(is_global=True)
class AuthModule(Module):
    """Full authentication and authorization stack (JWT, OAuth2/OIDC, RBAC, policies).

    Call :meth:`configure` to configure the auth bundle with an
    :class:`~quadkit.auth.config.AuthConfig`.

    Usage::

        from quadkit.auth.config import AuthConfig

        @module(
            imports=[AuthModule.configure(AuthConfig(secret_key="..."))]
        )
        class AppModule(Module):
            pass
    """

    @classmethod
    def configure(
        cls,
        config: Any | None = None,
        initial_roles: dict[str, Any] | None = None,
        is_global: bool = True,
        *,
        user_store: UserStoreProtocol | UserStoreKind | None = None,
        user_table: str | None = None,
        cache_service: Any = None,
        session_store: SessionStore | None = None,
    ) -> DynamicModule:
        """Create an AuthModule with explicit configuration.

        Args:
            config: :class:`~quadkit.auth.config.AuthConfig` or ``None``
                for framework defaults (development-only ephemeral secrets).
            initial_roles: Optional RBAC role seed forwarded to the
                authorization sub-provider.
            user_store: Host-owned store (or ``"memory"``/``"sql"`` kind) used
                by authentication. Defaults to in-memory storage; durable hosts
                must supply a persistent store. The host owns migrations and
                the store connection lifecycle.
            user_table: SQL identity table name. Ignored unless the resolved
                store kind is ``"sql"``.
            session_store: Explicit host-owned session backend. No migrations or
                cookie routes are enabled by supplying it.
            cache_service: Explicit host-owned token blacklist backend forwarded
                to authentication; must provide durable set/exists operations
                when the host promises persistent JWT revocation.

        Returns:
            A :class:`~quadkit.di.module.DynamicModule` descriptor.
        """
        from quadkit.auth.admin.contributor import AuthAdminContributor
        from quadkit.auth.admin.handlers.active_sessions import (
            ActiveSessionsWidgetHandler,
        )
        from quadkit.auth.admin.handlers.failed_logins import FailedLoginsWidgetHandler
        from quadkit.auth.admin.handlers.token_refresh_rate import (
            TokenRefreshRateWidgetHandler,
        )
        from quadkit.auth.di.bundle_provider import AuthBundleProvider

        return DynamicModule(
            module=cls,
            providers=[
                AuthBundleProvider(
                    config=config,
                    initial_roles=initial_roles,
                    user_store=user_store,
                    user_table=user_table,
                    cache_service=cache_service,
                    session_store=session_store,
                )
            ],
            exports=[
                AuthenticatorProtocol,
                AuthorizerProtocol,
                TokenManagerProtocol,
                PasswordHasherProtocol,
                AuthenticationService,
                AuthAdminContributor,
                ActiveSessionsWidgetHandler,
                FailedLoginsWidgetHandler,
                TokenRefreshRateWidgetHandler,
            ],
            is_global=is_global,
        )

    @classmethod
    def stub(cls, config: Any = None) -> DynamicModule:
        """Return an in-memory AuthModule suitable for unit and integration testing.

        Uses ephemeral in-memory storage with a fixed test secret key.
        No external token services, databases, or OAuth providers are
        configured.

        Args:
            config: Optional test configuration override.

        Returns:
            A DynamicModule backed by in-memory auth storage.
        """
        from quadkit.auth.config import AuthConfig, JWTConfig
        from quadkit.auth.di.bundle_provider import AuthBundleProvider

        return DynamicModule(
            module=cls,
            providers=[
                AuthBundleProvider(
                    config=AuthConfig(
                        secret_key="test-secret-key-for-testing-only",  # noqa: S106  # in-memory test bootstrap
                        token=JWTConfig(
                            secret_key="test-secret-key-for-testing-only",  # noqa: S106  # in-memory test bootstrap
                        ),
                    ),
                    initial_roles=None,
                )
            ],
            exports=[
                AuthenticatorProtocol,
                AuthorizerProtocol,
                TokenManagerProtocol,
                PasswordHasherProtocol,
                AuthenticationService,
            ],
        )


__all__ = ["AuthModule"]
