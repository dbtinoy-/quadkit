from __future__ import annotations

from dataclasses import dataclass

from quadkit.domain import DomainModel
from quadkit.validation import Field


@dataclass(init=False)
class LoginRequest(DomainModel):
    email: str = Field(..., description="Email address")
    password: str = Field(..., description="User password")
    remember_me: bool = Field(False, description="Remember login session")


@dataclass(init=False)
class RegisterRequest(DomainModel):
    name: str = Field(..., min_length=3, max_length=50, description="User name")
    email: str = Field(..., description="Valid email address")
    password: str = Field(..., min_length=8, description="Secure password")
    confirm_password: str = Field(..., description="Password confirmation")
    profile: dict = Field(
        default_factory=dict,
        description="Additional user profile data",
    )

    def validate_passwords_match(self) -> None:
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")


@dataclass(init=False)
class RefreshTokenRequest(DomainModel):
    refresh_token: str = Field(..., description="Valid refresh token")


@dataclass(init=False)
class PasswordResetRequest(DomainModel):
    email: str = Field(..., description="User email address")


@dataclass(init=False)
class PasswordResetConfirm(DomainModel):
    token: str = Field(..., description="Reset token")
    new_password: str = Field(..., min_length=8, description="New password")
    confirm_password: str = Field(..., description="Password confirmation")

    def validate_passwords_match(self) -> None:
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match")


@dataclass(init=False)
class OAuth2AuthorizeRequest(DomainModel):
    response_type: str = Field(..., description="Response type (code, token)")
    client_id: str = Field(..., description="OAuth2 client ID")
    redirect_uri: str | None = Field(None, description="Redirect URI")
    scope: str = Field("openid profile", description="Requested scopes")
    state: str | None = Field(None, description="State parameter")


@dataclass(init=False)
class OAuth2TokenRequest(DomainModel):
    grant_type: str = Field(..., description="Grant type")
    code: str | None = Field(None, description="Authorization code")
    redirect_uri: str | None = Field(None, description="Redirect URI")
    client_id: str | None = Field(None, description="Client ID")
    client_secret: str | None = Field(None, description="Client secret")
    refresh_token: str | None = Field(None, description="Refresh token")


__all__ = [
    "LoginRequest",
    "OAuth2AuthorizeRequest",
    "OAuth2TokenRequest",
    "PasswordResetConfirm",
    "PasswordResetRequest",
    "RefreshTokenRequest",
    "RegisterRequest",
]
