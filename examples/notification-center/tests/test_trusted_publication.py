"""Real native composition: authenticated publish, durable worker, scoped inbox."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import httpx
from notification_center.trusted.app import create_app
from notification_center.trusted.service import TrustedPublication
import pytest

from quadkit.config import QuadkitConfig
from quadkit.contracts.notification.delivery import DeliveryStatus
from quadkit.notification.delivery import flush_retries
from quadkit.primitives import clock
from quadkit.testing.fakes.clock import FakeClock
from quadkit.web import WebProvider


def settings(tmp_path):
    return QuadkitConfig(
        logging={"level": "ERROR"},
        sql={"backend": {"url": f"sqlite+aiosqlite:///{tmp_path / 'trusted.db'}"}},
        trusted_publication={
            "recipient_email": "editor@example.test",
            "token_secret": "test-only-secret-with-at-least-forty-characters",
        },
        web={
            "security": {"csrf": {"enabled": True, "exclude_auth_schemes": ["Bearer"]}}
        },
    )


@asynccontextmanager
async def running(config):
    app = create_app(config)
    await app.start()
    try:
        service = await app.container.resolve(TrustedPublication)
        web = await app.container.resolve(WebProvider)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(
                app=web.starlette, raise_app_exceptions=False
            ),
            base_url="http://testserver",
        ) as client:
            yield service, client
    finally:
        await app.stop()


async def accounts(service):
    owner = await service.users.create_user(
        "editor", "editor@example.test", None, permissions=["editorial:publish"]
    )
    other = await service.users.create_user("other", "other@example.test", None)
    auth = {"Authorization": "Bearer " + service.tokens.create_access_token(owner)}
    other_auth = {
        "Authorization": "Bearer " + service.tokens.create_access_token(other)
    }
    return owner, other, auth, other_auth


async def create(client, auth):
    response = await client.post(
        "/posts", json={"title": "durable needle"}, headers=auth
    )
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "draft"
    return response.json()["id"]


async def test_real_auth_atomic_enqueue_and_owner_scoped_http(tmp_path):
    async with running(settings(tmp_path)) as (service, client):
        owner, other, auth, other_auth = await accounts(service)
        spec = (await client.get("/openapi.json")).json()
        for path in (
            "/posts",
            "/posts/search",
            "/posts/{post_id}/publish",
            "/inbox",
            "/inbox/{message_id}",
            "/inbox/{message_id}/read",
        ):
            for operation in spec["paths"][path].values():
                assert operation["security"] == [{"bearerAuth": []}]
        assert (
            await client.get(
                "/inbox",
                headers=[
                    ("Authorization", auth["Authorization"]),
                    ("Authorization", "Bearer forged"),
                ],
            )
        ).status_code == 401
        assert (
            await client.get(
                "/inbox", params={"access_token": auth["Authorization"][7:]}
            )
        ).status_code == 401
        assert (await client.get("/inbox")).status_code == 401
        assert (
            await client.get("/inbox", headers={"Authorization": "Bearer forged"})
        ).status_code == 401
        assert (
            await client.post("/posts", json={"title": "forbidden"}, headers=other_auth)
        ).status_code == 403
        assert (
            await client.post(
                "/posts",
                json={"title": "spoof", "recipient_id": other.user_id},
                headers=auth,
            )
        ).status_code == 422
        key = await create(client, auth)
        assert (
            await client.post(
                f"/posts/{key}/publish",
                json={"recipient_id": other.user_id},
                headers=auth,
            )
        ).status_code == 422
        assert (await service.search("needle"))[0]["status"] == "draft"
        published = await client.post(f"/posts/{key}/publish", json={}, headers=auth)
        assert published.status_code == 202, published.text
        assert published.json()["notification"] == "queued"
        record = await service.queue.get_delivery(published.json()["delivery_id"])
        assert record.message.metadata == {
            "post_id": key,
            "status": "published",
            "effect_key": f"post-published:v1:{key}",
            "recipient_user_id": owner.user_id,
        }
        assert (await client.get("/inbox", headers=auth)).json() == {"items": []}
        assert await service.flush() == 1
        items = (await client.get("/inbox", headers=auth)).json()["items"]
        assert len(items) == 1
        assert items[0]["body"] == "durable needle"
        message_id = items[0]["id"]
        assert "metadata" not in items[0]
        assert "user_id" not in items[0]
        assert (
            await client.get(f"/inbox?user_id={owner.user_id}", headers=other_auth)
        ).json() == {"items": []}
        assert (
            await client.get(f"/inbox/{message_id}", headers=other_auth)
        ).status_code == 404
        assert (
            await client.post(f"/inbox/{message_id}/read", headers=other_auth)
        ).status_code == 204
        assert (
            await client.delete(f"/inbox/{message_id}", headers=other_auth)
        ).status_code == 204
        assert (await client.get(f"/inbox/{message_id}", headers=auth)).json()[
            "read"
        ] is False
        assert (
            await client.post(f"/inbox/{message_id}/read", headers=auth)
        ).status_code == 204
        assert (await client.get(f"/inbox/{message_id}", headers=auth)).json()[
            "read"
        ] is True
        assert (
            await client.post(f"/posts/{key}/publish", json={}, headers=auth)
        ).status_code == 409
        assert await service.flush() == 0
        assert len(await service.inbox.get_inbox(owner.user_id)) == 1
        assert (
            await client.post("/inbox", json={"user_id": other.user_id}, headers=auth)
        ).status_code == 405
        # Permission and active status are resolved again, not trusted JWT claims.
        owner.permissions = []
        await service.users.update_user(owner)
        assert (
            await client.post("/posts", json={"title": "forbidden"}, headers=auth)
        ).status_code == 403
        owner.is_active = False
        await service.users.update_user(owner)
        assert (await client.get("/inbox", headers=auth)).status_code == 401


async def test_enqueue_failure_rolls_back_publication_and_can_retry(tmp_path):
    config = settings(tmp_path)
    async with running(config) as (service, client):
        owner, _, auth, _ = await accounts(service)
        key = await create(client, auth)
        await execute_checked(
            service,
            "CREATE TRIGGER reject_editorial_queue BEFORE INSERT ON editorial_inbox_delivery BEGIN SELECT RAISE(ABORT, 'queue unavailable'); END",
        )
        failed = await client.post(f"/posts/{key}/publish", json={}, headers=auth)
        assert failed.status_code == 500, failed.text
        assert "queue unavailable" not in failed.text
        assert (await service.search("needle"))[0]["status"] == "draft"
        count = await service.database.execute_query(
            "SELECT COUNT(*) AS n FROM editorial_inbox_delivery"
        )
        assert count.rows[0]["n"] == 0
        assert await service.inbox.get_inbox(owner.user_id) == []
    async with running(config) as (service, client):
        await execute_checked(service, "DROP TRIGGER reject_editorial_queue")
        published = await client.post(f"/posts/{key}/publish", json={}, headers=auth)
        assert published.status_code == 202, published.text
        assert await service.flush() == 1
        assert len((await client.get("/inbox", headers=auth)).json()["items"]) == 1


@pytest.mark.parametrize("failure", ["insert", "acknowledgement"])
async def test_delivery_failure_and_cold_restart_recover_without_republishing(
    tmp_path, failure
):
    config = settings(tmp_path)
    timer = FakeClock(datetime.now(UTC))
    with clock.use(timer):
        async with running(config) as (service, client):
            owner, _, auth, _ = await accounts(service)
            key = await create(client, auth)
            await service.inbox.get_inbox(owner.user_id)
            response = await client.post(f"/posts/{key}/publish", json={}, headers=auth)
            assert response.status_code == 202, response.text
            delivery_id = response.json()["delivery_id"]
            if failure == "insert":
                await execute_checked(
                    service,
                    "CREATE TRIGGER reject_editorial_inbox BEFORE INSERT ON notification_inbox_messages BEGIN SELECT RAISE(ABORT, 'inbox unavailable'); END",
                )
                assert await service.flush() == 0
                assert await service.inbox.get_inbox(owner.user_id) == []
            else:
                service.queue.mark_delivered = AsyncMock(
                    side_effect=RuntimeError("acknowledgement lost")
                )
                with pytest.raises(RuntimeError, match="acknowledgement lost"):
                    await service.flush()
                assert len(await service.inbox.get_inbox(owner.user_id)) == 1
            assert (await service.search("needle"))[0]["status"] == "published"
        timer.advance(301)
        async with running(config) as (service, client):
            if failure == "insert":
                await execute_checked(service, "DROP TRIGGER reject_editorial_inbox")
            assert await service.flush() == 1
            record = await service.queue.get_delivery(delivery_id)
            assert record.status == DeliveryStatus.DELIVERED
            items = (await client.get("/inbox", headers=auth)).json()["items"]
            assert len(items) == 1
            assert (
                await service.channel.send(record.message)
            ).unwrap().message_id == items[0]["id"]
            assert (
                await client.post(f"/posts/{key}/publish", json={}, headers=auth)
            ).status_code == 409
            assert len(await service.inbox.get_inbox(owner.user_id)) == 1
            assert (
                await client.delete(f"/inbox/{items[0]['id']}", headers=auth)
            ).status_code == 204
            assert (await service.channel.send(record.message)).is_ok()
            assert (await client.get("/inbox", headers=auth)).json() == {"items": []}


async def test_missing_recipient_refuses_before_publication(tmp_path):
    async with running(settings(tmp_path)) as (service, client):
        publisher = await service.users.create_user(
            "publisher",
            "publisher@example.test",
            None,
            permissions=["editorial:publish"],
        )
        auth = {
            "Authorization": "Bearer " + service.tokens.create_access_token(publisher)
        }
        key = await create(client, auth)
        response = await client.post(f"/posts/{key}/publish", json={}, headers=auth)
        assert response.status_code == 503
        assert (await service.search("needle"))[0]["status"] == "draft"


async def execute_checked(service, sql):
    result = await service.database.execute(sql)
    assert result.success, result.error_message


async def test_ambiguous_oversized_and_routing_input_cannot_write(tmp_path):
    async with running(settings(tmp_path)) as (service, client):
        owner, _, auth, _ = await accounts(service)
        headers = {**auth, "Content-Type": "application/json"}
        duplicate_type = await client.post(
            "/posts",
            content='{"title":"ambiguous"}',
            headers=[
                ("Authorization", auth["Authorization"]),
                ("Content-Type", "application/json"),
                ("Content-Type", "text/plain"),
            ],
        )
        assert duplicate_type.status_code == 415
        cases = [
            ('{"title":"first","title":"second"}', 400),
            ('{"title":"first","recipient_id":"forged"}', 422),
            ('{"title":"first","status":"published"}', 422),
            ('{"title":NaN}', 422),
            ('{"title":"' + "x" * 5000 + '"}', 413),
            ("[]", 400),
        ]
        for body, status in cases:
            response = await client.post("/posts", content=body, headers=headers)
            assert response.status_code == status, response.text
        assert await service.search("") == []
        key = await create(client, auth)
        owner.is_active = False
        await service.users.update_user(owner)
        # A different genuine authorized publisher still cannot notify an inactive target.
        publisher = await service.users.create_user(
            "publisher",
            "publisher@example.test",
            None,
            permissions=["editorial:publish"],
        )
        publisher_auth = {
            "Authorization": "Bearer " + service.tokens.create_access_token(publisher)
        }
        response = await client.post(
            f"/posts/{key}/publish", json={}, headers=publisher_auth
        )
        assert response.status_code == 503
        assert (await service.search("needle"))[0]["status"] == "draft"
        count = await service.database.execute_query(
            "SELECT COUNT(*) AS n FROM editorial_inbox_delivery"
        )
        assert count.rows[0]["n"] == 0


async def test_terminal_delivery_has_explicit_safe_operator_redrive(tmp_path):
    async with running(settings(tmp_path)) as (service, client):
        owner, _, auth, _ = await accounts(service)
        key = await create(client, auth)
        await service.inbox.get_inbox(owner.user_id)
        response = await client.post(f"/posts/{key}/publish", json={}, headers=auth)
        assert response.status_code == 202
        delivery_id = response.json()["delivery_id"]
        with pytest.raises(ValueError, match="failed delivery"):
            await service.redrive(delivery_id)
        await execute_checked(
            service,
            "CREATE TRIGGER reject_terminal_inbox BEFORE INSERT ON notification_inbox_messages BEGIN SELECT RAISE(ABORT, 'inbox unavailable'); END",
        )
        assert (
            await flush_retries(service.queue, service.dispatcher, max_attempts=1) == 0
        )
        original = await service.queue.get_delivery(delivery_id)
        assert original.status == DeliveryStatus.FAILED
        await execute_checked(service, "DROP TRIGGER reject_terminal_inbox")
        replacement = await service.redrive(delivery_id)
        assert replacement != delivery_id
        new_record = await service.queue.get_delivery(replacement)
        assert new_record.message == original.message
        assert await service.flush() == 1
        assert (
            await service.queue.get_delivery(delivery_id)
        ).status == DeliveryStatus.FAILED
        assert (
            await service.queue.get_delivery(replacement)
        ).status == DeliveryStatus.DELIVERED
        assert (
            await client.post(f"/posts/{key}/publish", json={}, headers=auth)
        ).status_code == 409
        assert len(await service.inbox.get_inbox(owner.user_id)) == 1
        assert (
            await client.post(
                "/redrive", json={"delivery_id": delivery_id}, headers=auth
            )
        ).status_code == 404
