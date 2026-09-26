"""Admin management pages for quadkit-auth."""

from __future__ import annotations

from quadkit.auth.admin.pages.overview import AuthOverviewPage
from quadkit.auth.admin.pages.sessions import AuthSessionsPage
from quadkit.auth.admin.pages.tokens import AuthTokensPage
from quadkit.auth.admin.pages.users import AuthUsersPage

__all__ = [
    "AuthOverviewPage",
    "AuthSessionsPage",
    "AuthTokensPage",
    "AuthUsersPage",
]
