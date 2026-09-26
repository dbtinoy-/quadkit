"""Tests for the EventsHistoryPage admin page structured content."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from quadkit.contracts.admin import PageContent
from quadkit.contracts.admin.widget_content import TableContent
from quadkit.events.admin.pages import EventsHistoryPage


class FakeUrl:
    """Minimal URL stand-in exposing ``path`` and a string form."""

    path = "/admin/events/history"

    def __str__(self) -> str:
        return "http://testserver/admin/events/history"


class FakeRequest:
    """Minimal ASGI request stand-in with a URL."""

    query_params: dict[str, str] = {}
    url = FakeUrl()

    @classmethod
    def with_params(cls, **params: str) -> FakeRequest:
        request = cls()
        request.query_params = params
        return request


class FakeStore:
    """Stub event store holding events in insertion (oldest-first) order."""

    def __init__(self, events: list[object]) -> None:
        self._events = events

    async def read_all(
        self, position: int = 0, count: int | None = None
    ) -> list[object]:
        if count is None:
            return list(self._events)
        return self._events[position : position + count]


def _event(i: int) -> object:
    return SimpleNamespace(
        event_id=f"event-{i}",
        occurred_at=f"2026-01-01T00:00:{i:02d}",
    )


class TestEventsHistoryPage:
    """Unit tests for the recent-events page structured content."""

    @pytest.mark.asyncio
    async def test_returns_newest_first_rows_with_pagination(self) -> None:
        page = EventsHistoryPage(store=FakeStore([_event(i) for i in range(5)]))

        content = await page.handle(FakeRequest.with_params(per_page="2"))

        assert isinstance(content, PageContent)
        assert content.title == "Event History"
        assert isinstance(content.body, TableContent)
        assert len(content.body.rows) == 2
        assert content.body.rows[0][0].text == "event-4"
        assert content.body.rows[1][0].text == "event-3"
        assert content.pagination is not None
        assert content.pagination.page == 1
        assert content.pagination.total == 5
        assert content.pagination.per_page == 2
        assert content.pagination.base_url == "http://testserver/admin/events/history"

    @pytest.mark.asyncio
    async def test_single_page_returns_all_rows(self) -> None:
        page = EventsHistoryPage(store=FakeStore([_event(i) for i in range(2)]))

        content = await page.handle(FakeRequest())

        assert isinstance(content.body, TableContent)
        assert len(content.body.rows) == 2
        assert content.body.rows[0][0].text == "event-1"
        assert content.pagination is not None
        assert content.pagination.total == 2
        assert content.pagination.per_page == 20