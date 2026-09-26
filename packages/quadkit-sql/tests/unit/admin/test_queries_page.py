"""Tests for the SqlQueriesPage admin page structured content."""

from __future__ import annotations

from datetime import datetime

import pytest

from quadkit.contracts.admin import PageContent
from quadkit.contracts.admin.widget_content import TableContent
from quadkit.contracts.data.sql.query_log import QueryLogEntry
from quadkit.sql.admin.pages import SqlQueriesPage


class FakeUrl:
    """Minimal URL stand-in exposing ``path`` and a string form."""

    path = "/admin/sql/queries"

    def __str__(self) -> str:
        return "http://testserver/admin/sql/queries"


class FakeRequest:
    """Minimal ASGI request stand-in with a URL."""

    query_params: dict[str, str] = {}
    url = FakeUrl()

    @classmethod
    def with_params(cls, **params: str) -> FakeRequest:
        request = cls()
        request.query_params = params
        return request


class FakeQueryLogger:
    """Stub query logger returning a fixed set of entries."""

    def __init__(self, entries: list[QueryLogEntry]) -> None:
        self._entries = entries

    async def get_recent_queries(self, limit: int = 100) -> list[QueryLogEntry]:
        """Return the most recent entries, honouring *limit*."""
        return self._entries[-limit:]


def _entry(i: int) -> QueryLogEntry:
    return QueryLogEntry(
        sql=f"SELECT {i}",
        execution_time=0.01 * i,
        timestamp=datetime(2026, 1, 1, 0, 0, i),
    )


class TestSqlQueriesPage:
    """Unit tests for the recent-queries page structured content."""

    @pytest.mark.asyncio
    async def test_renders_pagination_when_many_entries(self) -> None:
        logger = FakeQueryLogger([_entry(i) for i in range(5)])
        page = SqlQueriesPage(query_logger=logger)

        content = await page.handle(FakeRequest.with_params(per_page="2"))

        assert isinstance(content, PageContent)
        assert content.title == "Recent Queries"
        assert isinstance(content.body, TableContent)
        assert content.body.columns == ("Query", "Duration", "Timestamp")
        assert len(content.body.rows) == 2
        assert content.body.rows[0][0].text == "SELECT 0"
        assert content.body.rows[1][0].text == "SELECT 1"
        assert content.pagination is not None
        assert content.pagination.page == 1
        assert content.pagination.total == 5
        assert content.pagination.per_page == 2
        assert content.pagination.base_url == "http://testserver/admin/sql/queries"

    @pytest.mark.asyncio
    async def test_second_page_slices_offsets(self) -> None:
        logger = FakeQueryLogger([_entry(i) for i in range(5)])
        page = SqlQueriesPage(query_logger=logger)

        content = await page.handle(FakeRequest.with_params(page="2", per_page="2"))

        assert isinstance(content.body, TableContent)
        assert content.body.rows[0][0].text == "SELECT 2"
        assert content.body.rows[1][0].text == "SELECT 3"
        assert content.pagination is not None
        assert content.pagination.page == 2
        assert content.pagination.total == 5
        assert content.pagination.per_page == 2

    @pytest.mark.asyncio
    async def test_single_page_renders_summary(self) -> None:
        logger = FakeQueryLogger([_entry(i) for i in range(2)])
        page = SqlQueriesPage(query_logger=logger)

        content = await page.handle(FakeRequest())

        assert isinstance(content.body, TableContent)
        assert len(content.body.rows) == 2
        assert content.body.rows[0][0].text == "SELECT 0"
        assert content.pagination is not None
        assert content.pagination.total == 2
        assert content.pagination.per_page == 20

    @pytest.mark.asyncio
    async def test_out_of_range_page_clamps_to_last(self) -> None:
        logger = FakeQueryLogger([_entry(i) for i in range(3)])
        page = SqlQueriesPage(query_logger=logger)

        content = await page.handle(FakeRequest.with_params(page="99", per_page="2"))

        assert isinstance(content.body, TableContent)
        assert content.body.rows[0][0].text == "SELECT 2"
        assert content.pagination is not None
        assert content.pagination.page == 2
