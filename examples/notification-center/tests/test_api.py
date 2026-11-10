"""Exercise the real notification-center composition root through HTTP."""

from __future__ import annotations

import httpx
import pytest


@pytest.mark.asyncio
async def test_inbox_is_seeded_with_sample_messages(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/notifications/inbox", params={"user_id": "demo-user"})
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 3
    titles = {m["title"] for m in data["messages"]}
    assert "Welcome to Notification Center" in titles


@pytest.mark.asyncio
async def test_health_endpoint(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/notifications/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["details"]["mailer"] == "healthy"
    assert body["details"]["sent_count"] == 0


@pytest.mark.asyncio
async def test_send_email_uses_the_real_mailer_protocol(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/api/notifications",
        json={"to": ["a@example.com"], "subject": "Hi", "body": "test body"},
    )
    assert response.status_code == 200
    receipt = response.json()
    assert receipt["backend"] == "console"
    assert receipt["channel"] == "email"
    assert receipt["message_id"]

    sent = (await client.get("/api/notifications/sent")).json()
    assert sent["count"] == 1
    assert sent["sent"][0]["subject"] == "Hi"
    assert sent["sent"][0]["status"] == "sent"


@pytest.mark.asyncio
async def test_send_email_requires_a_recipient(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/notifications", json={"to": [], "subject": "Hi", "body": "x"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_send_email_requires_a_subject(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/notifications", json={"to": ["a@example.com"], "subject": "", "body": "x"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_inbox_message_lifecycle(client: httpx.AsyncClient) -> None:
    created = await client.post(
        "/api/notifications/inbox",
        json={"user_id": "alice", "title": "Hello", "body": "World"},
    )
    assert created.status_code == 200
    message = created.json()["message"]
    message_id = message["id"]
    assert message["read"] is False

    unread = await client.get(
        "/api/notifications/inbox/unread-count", params={"user_id": "alice"}
    )
    assert unread.json()["unread_count"] == 1

    marked = await client.post(
        f"/api/notifications/inbox/message/{message_id}/read",
        params={"user_id": "alice"},
    )
    assert marked.status_code == 200

    listed = await client.get("/api/notifications/inbox", params={"user_id": "alice"})
    assert listed.json()["messages"][0]["read"] is True

    deleted = await client.delete(
        f"/api/notifications/inbox/message/{message_id}", params={"user_id": "alice"}
    )
    assert deleted.status_code == 200

    after = await client.get("/api/notifications/inbox", params={"user_id": "alice"})
    assert after.json()["count"] == 0


@pytest.mark.asyncio
async def test_mark_all_read_and_clear_inbox(client: httpx.AsyncClient) -> None:
    for i in range(3):
        await client.post(
            "/api/notifications/inbox",
            json={"user_id": "bob", "title": f"Msg {i}", "body": "body"},
        )

    unread_before = await client.get(
        "/api/notifications/inbox/unread-count", params={"user_id": "bob"}
    )
    assert unread_before.json()["unread_count"] == 3

    await client.post("/api/notifications/inbox/read-all", params={"user_id": "bob"})
    unread_after = await client.get(
        "/api/notifications/inbox/unread-count", params={"user_id": "bob"}
    )
    assert unread_after.json()["unread_count"] == 0

    cleared = await client.delete("/api/notifications/inbox", params={"user_id": "bob"})
    assert cleared.status_code == 200
    assert cleared.json()["deleted"] == 3

    empty = await client.get("/api/notifications/inbox", params={"user_id": "bob"})
    assert empty.json()["count"] == 0


@pytest.mark.asyncio
async def test_send_inbox_message_requires_a_title(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/notifications/inbox", json={"user_id": "carol", "title": "", "body": "x"}
    )
    assert response.status_code == 422
