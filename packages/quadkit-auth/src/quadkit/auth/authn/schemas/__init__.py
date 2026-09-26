"""Pydantic schemas for authentication requests and responses"""

from __future__ import annotations

from quadkit.auth.authn.schemas.requests import (
    LoginRequest,
    OAuth2AuthorizeRequest,
    OAuth2TokenRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenRequest,
    RegisterRequest,
)
from quadkit.auth.authn.schemas.responses import TokenResponse
from quadkit.auth.authn.schemas.user import UserProfile

__all__ = [
    "LoginRequest",
    "OAuth2AuthorizeRequest",
    "OAuth2TokenRequest",
    "PasswordResetConfirm",
    "PasswordResetRequest",
    "RefreshTokenRequest",
    "RegisterRequest",
    "TokenResponse",
    "UserProfile",
]
