"""Monitor stack UI assets and static-serving routes.

Convention followed: **Page controller pattern** — ``MonitorPageController``
serves static HTML/CSS/JS files.  The API controller handles all dynamic
behavior.

Exports:

- ``MonitorPageController`` — static file serving routes
"""

from __future__ import annotations

from monitorstack.ui.pages import MonitorPageController

__all__ = ["MonitorPageController"]
