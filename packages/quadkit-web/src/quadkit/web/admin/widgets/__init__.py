"""Web admin widgets — dashboard widget rendering for web server metrics.

This module provides widget handlers and rendering for the admin dashboard.
Each widget is contributed via the WebAdminContributor and dispatches
to a specific handler via registry-based lookup.
"""

from __future__ import annotations

from quadkit.web.admin.handlers.active_connections import (
    ActiveConnectionsWidgetHandler,
)
from quadkit.web.admin.handlers.request_rate import RequestRateWidgetHandler
from quadkit.web.admin.handlers.server_status import ServerStatusWidgetHandler

__all__ = [
    "ServerStatusWidgetHandler",
    "ActiveConnectionsWidgetHandler",
    "RequestRateWidgetHandler",
]
