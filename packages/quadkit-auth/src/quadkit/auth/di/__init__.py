"""Auth Providers - Framework integration and service registration"""

from __future__ import annotations

from quadkit.auth.authn.security import PasswordHasher, PasswordPolicy
from quadkit.auth.di.bundle_provider import AuthBundleProvider
from quadkit.auth.di.sub_providers.authentication_provider import (
    AuthenticationProvider,
)
from quadkit.auth.di.sub_providers.authorization_provider import AuthorizationProvider
from quadkit.auth.di.sub_providers.google_oauth_provider import GoogleOAuthProvider

__all__ = [
    "AuthBundleProvider",
    "AuthenticationProvider",
    "AuthorizationProvider",
    "GoogleOAuthProvider",
    "PasswordHasher",
    "PasswordPolicy",
]
