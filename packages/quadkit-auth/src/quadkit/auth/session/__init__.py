"""Session management for quadkit-auth."""

from __future__ import annotations

from quadkit.auth.session.cookie_backend import SessionCookieBackend
from quadkit.auth.session.hooks import (
    SessionCreatedHook,
    SessionExpiredHook,
    SessionRefreshedHook,
    SessionRevokedHook,
)
from quadkit.auth.session.manager import SessionManagerImpl

__all__ = [
    "SessionCookieBackend",
    "SessionCreatedHook",
    "SessionExpiredHook",
    "SessionManagerImpl",
    "SessionRefreshedHook",
    "SessionRevokedHook",
]
