"""Authentication and authorization protocols."""

from __future__ import annotations

from quadkit.contracts.auth.blacklist import TokenBlacklistProtocol
from quadkit.contracts.auth.exceptions import (
    AuthError,
    TokenError,
    VerificationError,
)
from quadkit.contracts.auth.guard import AuthenticatorProtocol, AuthorizerProtocol
from quadkit.contracts.auth.identity import IdentityResolverProtocol
from quadkit.contracts.auth.models import (
    UserIdentityProtocol,
    UserSession,
    VerifiedIdentityClaims,
)
from quadkit.contracts.auth.policy import PolicyStoreProtocol
from quadkit.contracts.auth.protocols import (
    AuthProviderProtocol,
    AuthSessionManagerProtocol,
    LoginAttemptTrackerProtocol,
    MFAManagerProtocol,
    PasswordHasherProtocol,
    PasswordPolicyProtocol,
)
from quadkit.contracts.auth.repositories import (
    APIKeyRepositoryProtocol,
    SessionRepositoryProtocol,
)
from quadkit.contracts.auth.roles import RoleDefinition
from quadkit.contracts.auth.store import (
    UserReaderProtocol,
    UserStoreProtocol,
    UserWriterProtocol,
)
from quadkit.contracts.auth.token import TokenManagerProtocol, VerifiedToken
from quadkit.contracts.auth.user import AuthenticatedUserProtocol, UserProtocol

__all__ = [
    "APIKeyRepositoryProtocol",
    "AuthError",
    "AuthProviderProtocol",
    "AuthSessionManagerProtocol",
    "AuthenticatedUserProtocol",
    "AuthenticatorProtocol",
    "AuthorizerProtocol",
    "IdentityResolverProtocol",
    "LoginAttemptTrackerProtocol",
    "MFAManagerProtocol",
    "PasswordHasherProtocol",
    "PasswordPolicyProtocol",
    "PolicyStoreProtocol",
    "RoleDefinition",
    "SessionRepositoryProtocol",
    "TokenBlacklistProtocol",
    "TokenError",
    "TokenManagerProtocol",
    "UserIdentityProtocol",
    "UserProtocol",
    "UserReaderProtocol",
    "UserSession",
    "UserStoreProtocol",
    "UserWriterProtocol",
    "VerificationError",
    "VerifiedIdentityClaims",
    "VerifiedToken",
]
