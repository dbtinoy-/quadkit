"""
quadkit-auth — Authentication and authorisation for the Quadkit platform.

Canonical import paths
-----------------------
User authentication:   from quadkit.auth.authn.services import AuthenticationService
Token refresh:         from quadkit.auth.authn.services import AuthenticationService
                       await service.refresh_token(existing_refresh_token)
JWT tokens:            from quadkit.auth.authn.jwt import JWTTokenManager
RBAC / authorisation:  from quadkit.auth.authz.service import AuthorizationService
Session management:    from quadkit.auth.session import SessionManagerImpl
OAuth:                 from quadkit.auth.authn.oauth import OAuthService
Account verification:  from quadkit.auth.authn.verification import AccountVerificationService

All commonly-used symbols are also re-exported from this root package so
``from quadkit.auth import JWTTokenManager`` always works.

Key APIs
--------
- ``AuthenticationService.refresh_token(refresh_token: str) -> Result[AuthToken, TokenError]``
  Refresh an expired access token using a refresh token. Returns new access + refresh tokens.
- ``AuthenticationService.authenticate(user_id, password) -> Result[AuthToken, AuthenticationFailed]``
  Authenticate a user with credentials.
- ``AuthorizationService.authorize(user, required_roles) -> Result[True, AuthorizationFailed]``
  Enforce RBAC policies.

GuardProtocol decorators
----------------
``use_guards`` is intentionally **not** exported from this root package.
Use ``quadkit.security.guards.use_guards`` (the canonical, general-purpose
version backed by ``GuardChain``) or the auth-specific decorators
``require_auth``, ``require_roles``, and ``require_permissions``.
"""

from __future__ import annotations

import importlib.metadata
from typing import TYPE_CHECKING, Any

__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from quadkit.auth.constants import __version__ as __version__

# =============================================================================
# Lazy Loading to Avoid Circular Imports
# =============================================================================


if TYPE_CHECKING:
    from quadkit.auth.authn.api_key import (
        APIKeyAuthenticator,
        APIKeyConfig,
    )
    from quadkit.auth.authn.google_oauth import GoogleOAuthService
    from quadkit.auth.authn.jwt import JWTTokenManager
    from quadkit.auth.authn.revocation import PersistentTokenRevocationStore
    from quadkit.auth.authn.security import (
        PasswordHasher,
        PasswordPolicy,
    )
    from quadkit.auth.authn.services import (
        AuthenticationService,
        LockoutConfig,
        LoginAttemptTracker,
    )
    from quadkit.auth.authn.user_service import UserService
    from quadkit.auth.authz.guards import (
        optional_auth,
        require_auth,
        require_permissions,
        require_roles,
    )
    from quadkit.auth.config import (
        AuthConfig,
        JWTConfig,
        MFAConfig,
        RBACConfig,
    )
    from quadkit.auth.di import (
        AuthenticationProvider,
        AuthorizationProvider,
        GoogleOAuthProvider,
    )
    from quadkit.auth.di.bundle_provider import AuthBundleProvider
    from quadkit.auth.events import (
        AuthenticationFailed,
        PasswordChanged,
        SessionCreated,
        SessionRevoked,
        TokenRevoked,
        UserAuthenticated,
        UserLockedOut,
        UserLoggedIn,
        UserLoggedOut,
        UserLoginFailed,
        UserRegistered,
    )
    from quadkit.auth.exceptions import (
        AlreadyVerifiedError,
        AuthenticationError,
        AuthError,
        AuthorizationError,
        InvalidTokenError,
        TokenAudienceError,
        TokenBlacklistedError,
        TokenError,
        TokenExpiredError,
        TokenExpiredVerificationError,
        TokenInvalidError,
        TokenNotFoundError,
        VerificationError,
    )
    from quadkit.auth.models import (
        AuthToken,
        User,
    )
    from quadkit.auth.protocols import TokenValidatorProtocol
    from quadkit.auth.session.cookie_backend import SessionCookieBackend
    from quadkit.auth.storage.oauth_identity_store import (
        MongoDBOAuthIdentityStore,
        OAuthIdentity,
        OAuthIdentityStore,
        SQLAlchemyOAuthIdentityStore,
    )
    from quadkit.auth.types import (
        AuthResult,
        AuthStatus,
        RoleDefinition,
        UserStatus,
    )
    from quadkit.contracts.auth import (
        IdentityResolverProtocol,
    )

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    # Session cookie backend
    "SessionCookieBackend": (
        "quadkit.auth.session.cookie_backend",
        "SessionCookieBackend",
    ),
    # Module
    "AuthModule": ("quadkit.auth.module", "AuthModule"),
    # Config
    "AuthConfig": ("quadkit.auth.config", "AuthConfig"),
    "JWTConfig": ("quadkit.auth.config", "JWTConfig"),
    "MFAConfig": ("quadkit.auth.config", "MFAConfig"),
    "RBACConfig": ("quadkit.auth.config", "RBACConfig"),
    # Providers
    "AuthBundleProvider": ("quadkit.auth.di.bundle_provider", "AuthBundleProvider"),
    "AuthenticationProvider": ("quadkit.auth.di", "AuthenticationProvider"),
    "AuthorizationProvider": ("quadkit.auth.di", "AuthorizationProvider"),
    "GoogleOAuthProvider": ("quadkit.auth.di", "GoogleOAuthProvider"),
    # Services
    "AuthenticationService": ("quadkit.auth.authn.services", "AuthenticationService"),
    "LoginAttemptTracker": ("quadkit.auth.authn.services", "LoginAttemptTracker"),
    "LockoutConfig": ("quadkit.auth.authn.services", "LockoutConfig"),
    "UserService": ("quadkit.auth.authn.user_service", "UserService"),
    # API Key AuthenticatorProtocol
    "APIKeyAuthenticator": ("quadkit.auth.authn.api_key", "APIKeyAuthenticator"),
    "APIKeyConfig": ("quadkit.auth.authn.api_key", "APIKeyConfig"),
    # Core Security
    "JWTTokenManager": ("quadkit.auth.authn.jwt", "JWTTokenManager"),
    "GoogleOAuthService": ("quadkit.auth.authn.google_oauth", "GoogleOAuthService"),
    "PasswordHasher": ("quadkit.auth.authn.security", "PasswordHasher"),
    "PasswordPolicy": ("quadkit.auth.authn.security", "PasswordPolicy"),
    # Token Revocation
    "PersistentTokenRevocationStore": (
        "quadkit.auth.authn.revocation",
        "PersistentTokenRevocationStore",
    ),
    # Types
    "User": ("quadkit.auth.models", "User"),
    "AuthToken": ("quadkit.auth.models", "AuthToken"),
    "AuthResult": ("quadkit.auth.types", "AuthResult"),
    "AuthStatus": ("quadkit.auth.types", "AuthStatus"),
    "UserStatus": ("quadkit.auth.types", "UserStatus"),
    "RoleDefinition": ("quadkit.auth.types", "RoleDefinition"),
    # OAuth Identity Store
    "OAuthIdentityStore": (
        "quadkit.auth.storage.oauth_identity_store",
        "OAuthIdentityStore",
    ),
    "OAuthIdentity": ("quadkit.auth.storage.oauth_identity_store", "OAuthIdentity"),
    "SQLAlchemyOAuthIdentityStore": (
        "quadkit.auth.storage.oauth_identity_store",
        "SQLAlchemyOAuthIdentityStore",
    ),
    "MongoDBOAuthIdentityStore": (
        "quadkit.auth.storage.oauth_identity_store",
        "MongoDBOAuthIdentityStore",
    ),
    # Protocols
    "IdentityResolverProtocol": (
        "quadkit.contracts.auth",
        "IdentityResolverProtocol",
    ),
    "OAuthIdentityStoreProtocol": (
        "quadkit.contracts.auth",
        "OAuthIdentityStoreProtocol",
    ),
    "TokenValidatorProtocol": (
        "quadkit.auth.protocols",
        "TokenValidatorProtocol",
    ),
    # Exceptions (all from single canonical exceptions.py)
    "AuthError": ("quadkit.auth.exceptions", "AuthError"),
    "AuthenticationError": ("quadkit.auth.exceptions", "AuthenticationError"),
    "AuthorizationError": ("quadkit.auth.exceptions", "AuthorizationError"),
    "TokenError": ("quadkit.auth.exceptions", "TokenError"),
    "InvalidTokenError": ("quadkit.auth.exceptions", "InvalidTokenError"),
    "TokenExpiredError": ("quadkit.auth.exceptions", "TokenExpiredError"),
    # Leaf token/verification exceptions (merged from former errors.py)
    "AlreadyVerifiedError": ("quadkit.auth.exceptions", "AlreadyVerifiedError"),
    "TokenAudienceError": ("quadkit.auth.exceptions", "TokenAudienceError"),
    "TokenBlacklistedError": ("quadkit.auth.exceptions", "TokenBlacklistedError"),
    "TokenExpiredVerificationError": (
        "quadkit.auth.exceptions",
        "TokenExpiredVerificationError",
    ),
    "TokenInvalidError": ("quadkit.auth.exceptions", "TokenInvalidError"),
    "TokenNotFoundError": ("quadkit.auth.exceptions", "TokenNotFoundError"),
    "VerificationError": ("quadkit.auth.exceptions", "VerificationError"),
    # Guards & Dependencies
    "require_auth": ("quadkit.auth.authz.guards", "require_auth"),
    "require_roles": ("quadkit.auth.authz.guards", "require_roles"),
    "require_permissions": ("quadkit.auth.authz.guards", "require_permissions"),
    "optional_auth": ("quadkit.auth.authz.guards", "optional_auth"),
    # Domain Events
    "AuthenticationFailed": ("quadkit.auth.events", "AuthenticationFailed"),
    "PasswordChanged": ("quadkit.auth.events", "PasswordChanged"),
    "SessionCreated": ("quadkit.auth.events", "SessionCreated"),
    "SessionRevoked": ("quadkit.auth.events", "SessionRevoked"),
    "TokenRevoked": ("quadkit.auth.events", "TokenRevoked"),
    "UserAuthenticated": ("quadkit.auth.events", "UserAuthenticated"),
    "UserLoggedIn": ("quadkit.auth.events", "UserLoggedIn"),
    "UserLoggedOut": ("quadkit.auth.events", "UserLoggedOut"),
    "UserLoginFailed": ("quadkit.auth.events", "UserLoginFailed"),
    "UserLockedOut": ("quadkit.auth.events", "UserLockedOut"),
    "UserRegistered": ("quadkit.auth.events", "UserRegistered"),
    # Hooks
    "AuthAuthenticationFailedHook": (
        "quadkit.auth.hooks",
        "AuthAuthenticationFailedHook",
    ),
    "AuthTokenIssuedHook": ("quadkit.auth.hooks", "AuthTokenIssuedHook"),
    "AuthTokenRefreshedHook": ("quadkit.auth.hooks", "AuthTokenRefreshedHook"),
    "AuthTokenRevokedHook": ("quadkit.auth.hooks", "AuthTokenRevokedHook"),
    "AuthUserAuthenticatedHook": ("quadkit.auth.hooks", "AuthUserAuthenticatedHook"),
}


def __getattr__(name: str) -> Any:
    """Lazy load attributes to avoid circular imports."""
    if name in _LAZY_IMPORTS:
        import importlib

        module_path, attr_name = _LAZY_IMPORTS[name]
        module = importlib.import_module(module_path)
        value = getattr(module, attr_name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """List available attributes for IDE support."""
    return list(__all__) + list(_LAZY_IMPORTS.keys())


__all__ = [
    "APIKeyAuthenticator",
    "APIKeyConfig",
    "AlreadyVerifiedError",
    "AuthAuthenticationFailedHook",
    "AuthBundleProvider",
    "AuthConfig",
    "AuthError",
    "AuthModule",
    "AuthResult",
    "AuthStatus",
    "AuthToken",
    "AuthTokenIssuedHook",
    "AuthTokenRefreshedHook",
    "AuthTokenRevokedHook",
    "AuthUserAuthenticatedHook",
    "AuthenticationFailed",
    "AuthenticationProvider",
    "AuthenticationService",
    "AuthorizationError",
    "AuthorizationProvider",
    "GoogleOAuthProvider",
    "GoogleOAuthService",
    "IdentityResolverProtocol",
    "InvalidTokenError",
    "JWTConfig",
    "JWTTokenManager",
    "LockoutConfig",
    "LoginAttemptTracker",
    "MFAConfig",
    "MongoDBOAuthIdentityStore",
    "OAuthIdentity",
    "OAuthIdentityStore",
    "PasswordChanged",
    "PasswordHasher",
    "PasswordPolicy",
    "PersistentTokenRevocationStore",
    "RBACConfig",
    "RoleDefinition",
    "SQLAlchemyOAuthIdentityStore",
    "SessionCookieBackend",
    "SessionCreated",
    "SessionRevoked",
    "TokenAudienceError",
    "TokenBlacklistedError",
    "TokenError",
    "TokenExpiredError",
    "TokenExpiredVerificationError",
    "TokenInvalidError",
    "TokenNotFoundError",
    "TokenRevoked",
    "TokenValidatorProtocol",
    "User",
    "UserAuthenticated",
    "UserLockedOut",
    "UserLoggedIn",
    "UserLoggedOut",
    "UserLoginFailed",
    "UserRegistered",
    "UserService",
    "UserStatus",
    "VerificationError",
    "optional_auth",
    "require_auth",
    "require_permissions",
    "require_roles",
]
