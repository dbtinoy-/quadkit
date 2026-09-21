"""Storefront UI assets and static-serving routes.

Convention followed: **Page controller pattern** — ``StorefrontPageController``
serves static HTML/CSS/JS files. Each module's own API controller handles
all dynamic behavior.

Exports:

- ``StorefrontPageController`` — static file serving routes
"""

from __future__ import annotations

from storefront.ui.pages import StorefrontPageController

__all__ = ["StorefrontPageController"]
