"""Tests for the quadkit-notification admin contributor."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.notification.admin import (
    InboxHandlers,
    NotificationAdminContributor,
)
from quadkit.serialization import loads


@pytest.fixture
def contributor() -> NotificationAdminContributor:
    return NotificationAdminContributor()


class TestNotificationAdminContributor:
    """Unit tests for the admin contributor surface."""

    def test_name_and_metadata(self, contributor: NotificationAdminContributor) -> None:
        assert contributor.name == "notifications"
        assert contributor.display_name == "Notifications"
        assert contributor.icon == "bell"

    def test_routes_expose_inbox_endpoints(
        self, contributor: NotificationAdminContributor
    ) -> None:
        routes = contributor.get_routes()
        paths = [(r.path, r.method) for r in routes]
        assert ("/admin/notifications/inbox", "GET") in paths
        assert ("/admin/notifications/read/{message_id}", "POST") in paths
        assert ("/admin/notifications/read-all", "POST") in paths

    def test_route_handlers_are_callable(
        self, contributor: NotificationAdminContributor
    ) -> None:
        for route in contributor.get_routes():
            assert callable(route.handler)

    def test_navigation_items(self, contributor: NotificationAdminContributor) -> None:
        nav = contributor.get_navigation_items()
        assert any(item.url == "/admin/notifications" for item in nav)

    def test_management_pages(self, contributor: NotificationAdminContributor) -> None:
        pages = contributor.get_management_pages()
        assert any(page.title == "Notifications Inbox" for page in pages)
        assert any(
            page.handler
            == "quadkit.notification.admin.pages.inbox:NotificationsInboxPage"
            for page in pages
        )

    def test_health_definitions(
        self, contributor: NotificationAdminContributor
    ) -> None:
        health = contributor.get_health_definitions()
        assert any(definition.name == "notifications.inbox" for definition in health)

    @pytest.mark.asyncio
    async def test_boot_resolves_inbox_service(self) -> None:
        from quadkit.notification.inbox.service import InboxService

        resolved = InboxService()

        class FakeLoader:
            async def resolve_optional(self, cls: Any) -> Any:
                return resolved

        contributor = NotificationAdminContributor()
        await contributor.on_admin_boot(FakeLoader())  # type: ignore[arg-type]
        assert contributor._handlers._service is resolved  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_boot_falls_back_when_service_unregistered(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Boot without InboxService bound must stay silent and use memory store."""

        class FakeLoader:
            async def resolve_optional(self, cls: Any) -> None:
                return None

        contributor = NotificationAdminContributor()
        with caplog.at_level("WARNING"):
            await contributor.on_admin_boot(FakeLoader())  # type: ignore[arg-type]
        assert contributor._handlers._service is None  # noqa: SLF001
        assert not [r for r in caplog.records if r.levelname == "WARNING"]


class FakeUser:
    """Stub user attached to requests."""

    id = "user-1"


class FakeRequest:
    """Minimal ASGI request stand-in."""

    user = FakeUser()
    query_params: dict[str, str] = {}
    method = "GET"


class TestInboxHandlers:
    """Unit tests for the inbox JSON handlers."""

    @pytest.fixture
    def handlers(self) -> InboxHandlers:
        return InboxHandlers()

    @pytest.mark.asyncio
    async def test_get_inbox_returns_empty_for_anon(
        self, handlers: InboxHandlers
    ) -> None:
        request = FakeRequest()
        request.user = None
        response = await handlers.get_inbox(request)  # type: ignore[arg-type]
        body = loads(response.body)
        assert body["unread_count"] == 0
        assert body["notifications"] == []

    @pytest.mark.asyncio
    async def test_get_inbox_round_trips(self, handlers: InboxHandlers) -> None:
        from quadkit.notification.inbox.service import InboxService

        service = InboxService()
        await service.send("user-1", title="Hello", body="World")

        handlers = InboxHandlers(service=service)
        request = FakeRequest()
        response = await handlers.get_inbox(request)  # type: ignore[arg-type]
        body = loads(response.body)
        assert body["unread_count"] == 1
        assert body["notifications"][0]["title"] == "Hello"

    @pytest.mark.asyncio
    async def test_mark_read_updates_store(self, handlers: InboxHandlers) -> None:
        from quadkit.notification.inbox.service import InboxService

        service = InboxService()
        await service.send("user-1", title="Hello", body="World")
        message = (await service.get_inbox("user-1"))[0]

        handler = InboxHandlers(service=service)
        request = FakeRequest()
        request.method = "POST"
        request.path_params = {"message_id": message.id}
        response = await handler.mark_read(request)  # type: ignore[arg-type]
        assert loads(response.body)["ok"] is True
        assert await service.count_unread("user-1") == 0

    @pytest.mark.asyncio
    async def test_mark_all_read_updates_store(self, handlers: InboxHandlers) -> None:
        from quadkit.notification.inbox.service import InboxService

        service = InboxService()
        await service.send("user-1", title="Hello", body="World")

        handler = InboxHandlers(service=service)
        request = FakeRequest()
        request.method = "POST"
        response = await handler.mark_all_read(request)  # type: ignore[arg-type]
        assert loads(response.body)["ok"] is True
        assert await service.count_unread("user-1") == 0

    @pytest.mark.asyncio
    async def test_mark_read_requires_auth(self, handlers: InboxHandlers) -> None:
        request = FakeRequest()
        request.user = None
        request.path_params = {"message_id": "m-1"}
        response = await handlers.mark_read(request)  # type: ignore[arg-type]
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_health_probe(self, handlers: InboxHandlers) -> None:
        message = await handlers.health()
        assert "inbox service not initialized" in message
