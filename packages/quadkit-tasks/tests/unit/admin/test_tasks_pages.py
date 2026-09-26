"""Tests for the task admin pages structured content."""

from __future__ import annotations

import pytest

from quadkit.contracts.admin import PageContent
from quadkit.contracts.admin.widget_content import TableContent
from quadkit.tasks.admin.pages import TasksFailedPage, TasksHistoryPage
from quadkit.tasks.models import JobResult
from quadkit.tasks.results import InMemoryResultStore


class FakeUrl:
    """Minimal URL stand-in exposing ``path`` and a string form."""

    def __init__(self, path: str = "/admin/tasks") -> None:
        self.path = path

    def __str__(self) -> str:
        """Return the URL as a string (without query params)."""
        return f"http://testserver{self.path}"


class FakeRequest:
    """Minimal ASGI request stand-in with a URL."""

    query_params: dict[str, str] = {}
    url = FakeUrl()

    @classmethod
    def with_params(cls, path: str, **params: str) -> FakeRequest:
        """Build a request whose path and query params are set explicitly."""
        request = cls()
        request.url = FakeUrl(path)
        request.query_params = params
        return request


class TestTasksHistoryPage:
    """Unit tests for the completed-tasks history page."""

    @pytest.mark.asyncio
    async def test_renders_completed_tasks_newest_first(self) -> None:
        """Completed results render newest first with a summary."""
        store = InMemoryResultStore()
        for i in range(3):
            await store.store(
                f"job-{i}",
                JobResult(success=True, id=f"job-{i}", name=f"task-{i}"),
            )

        page = TasksHistoryPage(result_store=store)
        content = await page.handle(FakeRequest.with_params("/admin/tasks/history"))

        assert isinstance(content, PageContent)
        assert content.title == "Task History"
        assert isinstance(content.body, TableContent)
        assert len(content.body.rows) == 3
        assert content.body.rows[0][0].text == "job-2"
        assert any(row[1].text == "task-0" for row in content.body.rows)
        assert content.pagination is not None
        assert content.pagination.page == 1
        assert content.pagination.total == 3
        assert content.pagination.per_page == 20
        assert content.pagination.base_url == "http://testserver/admin/tasks/history"

    @pytest.mark.asyncio
    async def test_renders_pagination_when_many(self) -> None:
        """Pagination controls and slicing render when data spills pages."""
        store = InMemoryResultStore()
        for i in range(5):
            await store.store(
                f"job-{i}",
                JobResult(success=True, id=f"job-{i}", name=f"task-{i}"),
            )

        page = TasksHistoryPage(result_store=store)
        content = await page.handle(
            FakeRequest.with_params("/admin/tasks/history", per_page="2")
        )

        assert isinstance(content.body, TableContent)
        assert len(content.body.rows) == 2
        assert content.body.rows[0][0].text == "job-4"
        assert content.body.rows[1][0].text == "job-3"
        assert content.pagination is not None
        assert content.pagination.page == 1
        assert content.pagination.total == 5
        assert content.pagination.per_page == 2

    @pytest.mark.asyncio
    async def test_out_of_range_page_clamps_to_last(self) -> None:
        """Pages past the last page clamp to the final slice."""
        store = InMemoryResultStore()
        for i in range(5):
            await store.store(
                f"job-{i}",
                JobResult(success=True, id=f"job-{i}", name=f"task-{i}"),
            )

        page = TasksHistoryPage(result_store=store)
        content = await page.handle(
            FakeRequest.with_params("/admin/tasks/history", page="99", per_page="2")
        )

        assert isinstance(content.body, TableContent)
        assert len(content.body.rows) == 1
        assert content.body.rows[0][0].text == "job-0"
        assert content.pagination is not None
        assert content.pagination.page == 3
        assert content.pagination.total == 5


class TestTasksFailedPage:
    """Unit tests for the failed-tasks page."""

    @pytest.mark.asyncio
    async def test_renders_failed_tasks_with_error_and_pagination(self) -> None:
        """Failed results show their error and honour pagination."""
        store = InMemoryResultStore()
        for i in range(5):
            await store.store(
                f"job-{i}",
                JobResult(
                    success=False,
                    id=f"job-{i}",
                    name=f"task-{i}",
                    error=f"boom-{i}",
                ),
            )

        page = TasksFailedPage(result_store=store)
        content = await page.handle(
            FakeRequest.with_params("/admin/tasks/failed", per_page="2")
        )

        assert isinstance(content, PageContent)
        assert content.title == "Failed Tasks"
        assert isinstance(content.body, TableContent)
        assert len(content.body.rows) == 2
        assert content.body.rows[0][0].text == "job-4"
        assert content.body.rows[1][0].text == "job-3"
        assert content.body.rows[0][3].text == "Failed"
        assert content.body.rows[0][4].text == "boom-4"
        assert content.body.rows[1][4].text == "boom-3"
        assert content.pagination is not None
        assert content.pagination.page == 1
        assert content.pagination.total == 5
        assert content.pagination.per_page == 2
        assert content.pagination.base_url == "http://testserver/admin/tasks/failed"
