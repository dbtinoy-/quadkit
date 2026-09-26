"""Authentication (AuthN) - Identity verification and session management"""

from __future__ import annotations

from quadkit.auth.authn._binding import TokenBindingConfig
from quadkit.auth.authn.account_verification import AccountVerificationService
from quadkit.auth.authn.api_key import APIKeyAuthenticator, APIKeyConfig
from quadkit.auth.authn.blacklist import JWTBlacklist
from quadkit.auth.authn.google_oauth import GoogleOAuthService
from quadkit.auth.authn.jwt import JWTTokenManager
from quadkit.auth.authn.oauth2 import OAuth2IdentityProvider, OAuth2Manager
from quadkit.auth.authn.password_reset import PasswordResetService
from quadkit.auth.authn.relay import RelayApiKeyVerifier
from quadkit.auth.authn.schemas import (
    LoginRequest,
    OAuth2AuthorizeRequest,
    OAuth2TokenRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
    UserProfile,
)
from quadkit.auth.authn.security import PasswordHasher, PasswordPolicy
from quadkit.auth.authn.services import (
    AuthenticationService,
    LockoutConfig,
    LoginAttemptTracker,
)
from quadkit.auth.authn.user_service import UserService
from quadkit.auth.models.user import User
from quadkit.contracts.auth.user import AuthenticatedUserProtocol

__all__ = [
    "APIKeyAuthenticator",
    "APIKeyConfig",
    "AccountVerificationService",
    "AuthenticatedUserProtocol",
    "AuthenticationService",
    "GoogleOAuthService",
    "JWTBlacklist",
    "JWTTokenManager",
    "LockoutConfig",
    "LoginAttemptTracker",
    "LoginRequest",
    "OAuth2AuthorizeRequest",
    "OAuth2IdentityProvider",
    "OAuth2Manager",
    "OAuth2TokenRequest",
    "PasswordHasher",
    "PasswordPolicy",
    "PasswordResetConfirm",
    "PasswordResetRequest",
    "PasswordResetService",
    "RefreshTokenRequest",
    "RegisterRequest",
    "RelayApiKeyVerifier",
    "TokenBindingConfig",
    "TokenResponse",
    "User",
    "UserProfile",
    "UserService",
]
