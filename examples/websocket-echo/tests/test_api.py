"""Exercise the real websocket-echo composition root, sockets included."""

from __future__ import annotations

import pytest

from quadkit.testing import WebTestBed

from websocket_echo.app import create_app


@pytest.mark.asyncio
async def test_hello_handshake_and_echo_roundtrip():
    async with WebTestBed(create_app()) as bed:
        with bed.client.websocket_connect("/ws/echo/lobby") as ws:
            hello = ws.receive_json()
            assert hello == {"type": "hello", "room": "lobby", "member": 1}

            ws.send_json({"text": "ping"})
            echo = ws.receive_json()
            assert echo["type"] == "echo"
            assert echo["data"] == {"text": "ping"}
            assert echo["room"] == "lobby"


@pytest.mark.asyncio
async def test_membership_counts_across_connections():
    async with WebTestBed(create_app()) as bed:
        with bed.client.websocket_connect("/ws/echo/lobby") as first:
            first_hello = first.receive_json()
            with bed.client.websocket_connect("/ws/echo/lobby") as second:
                second_hello = second.receive_json()
                assert second_hello["member"] == first_hello["member"] + 1


@pytest.mark.asyncio
async def test_stats_endpoint_reflects_join_and_leave():
    async with WebTestBed(create_app()) as bed:
        with bed.client.websocket_connect("/ws/echo/ops"):
            stats = bed.get("/stats")
            stats.assert_status(200)
            assert stats.json["rooms"]["ops"] == 1
        stats_after = bed.get("/stats")
        assert stats_after.json["rooms"]["ops"] == 0


@pytest.mark.asyncio
async def test_room_cap_refuses_extra_members(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("QK_WEBSOCKET_ECHO__MAX_ROOM_MEMBERS", "1")
    async with WebTestBed(create_app()) as bed:
        with bed.client.websocket_connect("/ws/echo/capped") as first:
            hello = first.receive_json()
            assert hello["member"] == 1
            with bed.client.websocket_connect("/ws/echo/capped") as second:
                refusal = second.receive_json()
                assert refusal == {
                    "type": "error",
                    "reason": "room-full",
                    "room": "capped",
                }


@pytest.mark.asyncio
async def test_index_describes_the_demo():
    async with WebTestBed(create_app()) as bed:
        index = bed.get("/")
        index.assert_status(200)
        assert index.json["demo"] == "websocket-echo"
        assert isinstance(index.json["endpoints"], list) and index.json["endpoints"]
