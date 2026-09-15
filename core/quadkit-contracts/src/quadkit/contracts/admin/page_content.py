"""Structured content for management pages contributed to the admin dashboard.

Contributors return ``PageContent`` instead of raw HTML so the host owns all
page markup. ``body`` reuses the ``WidgetContent`` union — the same renderer
used for dashboard widgets renders page bodies.
"""

from __future__ import annotations

from dataclasses import dataclass

from quadkit.contracts.admin.widget_content import WidgetContent


@dataclass(frozen=True)
class PaginationContent:
    """Pagination state for a structured management page."""

    page: int
    total: int
    per_page: int
    base_url: str


@dataclass(frozen=True)
class PageContent:
    """A management page contributed as structured content — never raw HTML."""

    title: str
    body: WidgetContent
    pagination: PaginationContent | None = None


__all__ = ["PageContent", "PaginationContent"]
