"""Real ASGI/SQLite checks for the recipient-scoped inbox adapter."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from starlette.applications import Starlette
from starlette.requests import Request

from quadkit.notification.inbox.database import DatabaseInboxStore
from quadkit.notification.inbox.http import InboxHttpAdapter
from quadkit.notification.inbox.service import InboxService


@pytest.mark.asyncio
async def test_inbox_http_separates_recipients_and_exposes_no_send(
    tmp_path: Path,
) -> None:
    SQLiteProvider = pytest.importorskip(
        "quadkit.sql.providers.sqlite_provider"
    ).SQLiteProvider
    provider = SQLiteProvider(str(tmp_path / "http.sqlite"))
    await provider.connect()
    try:
        service = InboxService(DatabaseInboxStore(provider))
        alice = await service.send("alice", "Alice", "Secret", internal="not exposed")
        bob = await service.send("bob", "Bob", "His")

        async def resolve_subject(request: Request) -> str | None:
            # Test-only token table; a production host must verify real credentials.
            return {"Bearer test-alice": "alice", "Bearer test-bob": "bob"}.get(
                request.headers.get("authorization", "")
            )

        adapter = InboxHttpAdapter(service, resolve_subject)
        app = Starlette(routes=adapter.routes("/notifications"))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            a = {"Authorization": "Bearer test-alice"}
            b = {"Authorization": "Bearer test-bob"}
            assert (await client.get("/notifications")).status_code == 401
            # Supplying a recipient in query/body/header never selects that inbox.
            listing = await client.get("/notifications?user_id=alice", headers=b)
            assert listing.status_code == 200
            assert [item["id"] for item in listing.json()["items"]] == [bob.id]
            assert "internal" not in listing.text
            assert (
                await client.get(f"/notifications/{alice.id}", headers=a)
            ).status_code == 200
            denied = await client.get(f"/notifications/{alice.id}", headers=b)
            missing = await client.get("/notifications/missing", headers=b)
            assert (denied.status_code, denied.json()) == (
                missing.status_code,
                missing.json(),
            )
            assert denied.status_code == 404
            assert (
                await client.post(f"/notifications/{alice.id}/read", headers=b)
            ).status_code == 204
            assert (
                await client.delete(f"/notifications/{alice.id}", headers=b)
            ).status_code == 204
            unchanged = await service.get_message_for_user(alice.id, "alice")
            assert unchanged is not None
            assert unchanged.read is False
            assert (
                await client.post(
                    "/notifications", headers=b, json={"user_id": "alice"}
                )
            ).status_code == 405
            assert (
                await client.get("/notifications?limit=0", headers=a)
            ).status_code == 400
            assert (
                await client.get("/notifications?offset=-1", headers=a)
            ).status_code == 400
            assert (
                await client.get(f"/notifications?offset={2**63}", headers=a)
            ).status_code == 400
            assert (
                await client.get(f"/notifications?offset={2**63 - 1}", headers=a)
            ).json() == {"items": []}
            assert (
                await client.post(f"/notifications/{alice.id}/read", headers=a)
            ).status_code == 204
            assert (await service.get_message_for_user(alice.id, "alice")).read is True
            assert (
                await client.delete(f"/notifications/{alice.id}", headers=a)
            ).status_code == 204
            assert await service.get_message_for_user(alice.id, "alice") is None
    finally:
        await provider.disconnect()


@pytest.mark.asyncio
async def test_invalid_resolver_result_is_not_an_authenticated_subject() -> None:
    async def missing_subject(_request: Request) -> str | None:
        return " "

    adapter = InboxHttpAdapter(InboxService(), missing_subject)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=Starlette(routes=adapter.routes())),
        base_url="http://test",
    ) as client:
        assert (await client.get("/inbox")).status_code == 401
        assert (await client.get("/inbox/any")).status_code == 401
        assert (await client.post("/inbox/any/read")).status_code == 401
        assert (await client.delete("/inbox/any")).status_code == 401


@pytest.mark.asyncio
async def test_store_failure_is_not_reported_as_an_empty_inbox() -> None:
    class BrokenService(InboxService):
        async def get_inbox(
            self,
            user_id: str,
            *,
            unread_only: bool = False,
            limit: int | None = None,
            offset: int = 0,
        ) -> list:
            raise RuntimeError("database unavailable")

    async def subject(_request: Request) -> str | None:
        return "alice"

    adapter = InboxHttpAdapter(BrokenService(), subject)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(
            app=Starlette(routes=adapter.routes()), raise_app_exceptions=False
        ),
        base_url="http://test",
    ) as client:
        assert (await client.get("/inbox")).status_code == 500


@pytest.mark.parametrize(
    "prefix", ["inbox", "/", "/inbox/", "/{user}", "/inbox//x", "/inbox?x=y"]
)
def test_inbox_prefix_must_be_explicit(prefix: str) -> None:
    async def subject(_request: Request) -> str | None:
        return None

    with pytest.raises(ValueError, match="inbox prefix"):
        InboxHttpAdapter(InboxService(), subject).routes(prefix)


@pytest.mark.asyncio
async def test_inbox_http_never_returns_a_mis_scoped_store_page() -> None:
    from quadkit.contracts.notification.inbox import InboxMessage

    secret = InboxMessage.create("alice", "Alice private title", "Alice secret")

    class BrokenStore:
        async def list_page_for_user(self, user_id, **kwargs):
            return [secret]

    async def subject(_request: Request) -> str | None:
        return "bob"

    adapter = InboxHttpAdapter(InboxService(BrokenStore()), subject)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(
            app=Starlette(routes=adapter.routes()), raise_app_exceptions=False
        ),
        base_url="http://test",
    ) as client:
        response = await client.get("/inbox")
        assert response.status_code == 500
        assert "Alice" not in response.text
        assert secret.id not in response.text
