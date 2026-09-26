"""Auth DI sub-providers — individual focused providers for the auth stack."""

from __future__ import annotations

from quadkit.auth.di.sub_providers.authentication_provider import (
    AuthenticationProvider,
)
from quadkit.auth.di.sub_providers.authorization_provider import AuthorizationProvider
from quadkit.auth.di.sub_providers.google_oauth_provider import GoogleOAuthProvider
from quadkit.auth.di.sub_providers.mfa_provider import MFAProvider
from quadkit.auth.di.sub_providers.oauth2_provider import OAuth2Provider
from quadkit.auth.di.sub_providers.oauth_provider import (
    detect_oauth_providers_from_config,
)
from quadkit.auth.di.sub_providers.passkey_provider import PasskeyProvider
from quadkit.auth.di.sub_providers.session_provider import SessionProvider
from quadkit.auth.di.sub_providers.token_provider import TokenProvider

__all__ = [
    "AuthenticationProvider",
    "AuthorizationProvider",
    "GoogleOAuthProvider",
    "MFAProvider",
    "OAuth2Provider",
    "PasskeyProvider",
    "SessionProvider",
    "TokenProvider",
    "detect_oauth_providers_from_config",
]
