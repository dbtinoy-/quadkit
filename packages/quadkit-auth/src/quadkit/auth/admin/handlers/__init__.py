"""Widget handlers for auth admin dashboard."""

from __future__ import annotations

from quadkit.auth.admin.handlers.active_sessions import ActiveSessionsWidgetHandler
from quadkit.auth.admin.handlers.failed_logins import FailedLoginsWidgetHandler
from quadkit.auth.admin.handlers.token_refresh_rate import (
    TokenRefreshRateWidgetHandler,
)

__all__ = [
    "ActiveSessionsWidgetHandler",
    "FailedLoginsWidgetHandler",
    "TokenRefreshRateWidgetHandler",
]
