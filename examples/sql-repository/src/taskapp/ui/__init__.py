"""Task manager UI assets and static-serving routes.

Convention followed: **Page controller pattern** — ``TasksPageController``
serves static HTML/CSS/JS files.  The API controller handles all dynamic
behavior.

Exports:

- ``TasksPageController`` — static file serving routes
"""

from __future__ import annotations

from taskapp.ui.pages import TasksPageController

__all__ = ["TasksPageController"]
