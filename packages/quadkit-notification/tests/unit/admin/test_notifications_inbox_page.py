"""Tests for the NotificationsInboxPage admin page structured content."""

from __future__ import annotations

import pytest

from quadkit.contracts.admin import PageContent
from quadkit.contracts.admin.widget_content import EmptyContent, TableContent
from quadkit.notification.admin import NotificationsInboxPage
from quadkit.notification.inbox.service import InboxService


class FakeUrl:
    """Minimal URL stand-in exposing ``path`` and a string form."""

    path = "/admin/notifications"

    def __str__(self) -> str:
        return "http://testserver/admin/notifications"


class FakeUser:
    """Stub user attached to requests."""

    id = "user-1"


class FakeRequest:
    """Minimal ASGI request stand-in with query params and a URL."""

    user = FakeUser()
    query_params: dict[str, str] = {}
    url = FakeUrl()

    @classmethod
    def with_params(cls, **params: str) -> FakeRequest:
        request = cls()
        request.query_params = params
        return request


class TestNotificationsInboxPage:
    """Unit tests for the inbox page structured content."""

    @pytest.mark.asyncio
    async def test_returns_paginated_message_rows(self) -> None:
        service = InboxService()
        await service.send("user-1", title="Hello", body="World")

        page = NotificationsInboxPage(inbox_service=service)
        content = await page.handle(FakeRequest())

        assert isinstance(content, PageContent)
        assert content.title == "Notifications Inbox"
        assert isinstance(content.body, TableContent)
        assert len(content.body.rows) == 1
        assert content.body.rows[0][0].text == "Hello"
        assert content.body.rows[0][1].text == "World"
        assert content.pagination is not None
        assert content.pagination.page == 1
        assert content.pagination.total == 1
        assert content.pagination.per_page == 20
        assert content.pagination.base_url == "http://testserver/admin/notifications"

    @pytest.mark.asyncio
    async def test_returns_empty_content_for_anon(self) -> None:
        page = NotificationsInboxPage()
        request = FakeRequest()
        request.user = None
        content = await page.handle(request)

        assert isinstance(content, PageContent)
        assert content.title == "Notifications Inbox"
        assert isinstance(content.body, EmptyContent)
        assert content.body.title == "No Notifications"
        assert content.body.icon == "inbox"

    @pytest.mark.asyncio
    async def test_honors_limit(self) -> None:
        service = InboxService()
        for i in range(5):
            await service.send("user-1", title=f"T{i}", body=f"B{i}")

        page = NotificationsInboxPage(inbox_service=service)
        content = await page.handle(FakeRequest.with_params(limit="2"))

        assert isinstance(content.body, TableContent)
        assert len(content.body.rows) == 2
        assert content.body.rows[0][0].text == "T4"
        assert content.body.rows[1][0].text == "T3"
        assert content.pagination is not None
        assert content.pagination.total == 5
        assert content.pagination.per_page == 2

    @pytest.mark.asyncio
    async def test_paginates_page_two(self) -> None:
        service = InboxService()
        for i in range(5):
            await service.send("user-1", title=f"T{i}", body=f"B{i}")

        page = NotificationsInboxPage(inbox_service=service)
        content = await page.handle(FakeRequest.with_params(page="2", per_page="2"))

        assert isinstance(content.body, TableContent)
        assert [row[0].text for row in content.body.rows] == ["T2", "T1"]
        assert content.pagination is not None
        assert content.pagination.page == 2

    @pytest.mark.asyncio
    async def test_extra_page_has_remaining_item(self) -> None:
        service = InboxService()
        for i in range(5):
            await service.send("user-1", title=f"T{i}", body=f"B{i}")

        page = NotificationsInboxPage(inbox_service=service)
        content = await page.handle(FakeRequest.with_params(page="3", per_page="2"))

        assert isinstance(content.body, TableContent)
        assert [row[0].text for row in content.body.rows] == ["T0"]
        assert content.pagination is not None
        assert content.pagination.page == 3

    @pytest.mark.asyncio
    async def test_clamps_page_beyond_end(self) -> None:
        service = InboxService()
        for i in range(5):
            await service.send("user-1", title=f"T{i}", body=f"B{i}")

        page = NotificationsInboxPage(inbox_service=service)
        content = await page.handle(FakeRequest.with_params(page="99", per_page="2"))

        assert isinstance(content.body, TableContent)
        assert [row[0].text for row in content.body.rows] == ["T0"]
        assert content.pagination is not None
        assert content.pagination.page == 3
