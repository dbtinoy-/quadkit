"""Admin dashboard widgets and contributor for quadkit-auth."""

from __future__ import annotations

from quadkit.auth.admin.contributor import AuthAdminContributor
from quadkit.auth.admin.handlers import (
    ActiveSessionsWidgetHandler,
    FailedLoginsWidgetHandler,
    TokenRefreshRateWidgetHandler,
)

__all__ = [
    "ActiveSessionsWidgetHandler",
    "AuthAdminContributor",
    "FailedLoginsWidgetHandler",
    "TokenRefreshRateWidgetHandler",
]
