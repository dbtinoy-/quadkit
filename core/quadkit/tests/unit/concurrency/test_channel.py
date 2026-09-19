"""Tests for M27: OTEL context propagation through BoundedChannel."""

import contextvars

import pytest

from quadkit.concurrency.channels.channel import BoundedChannel

REQUEST_ID: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


class TestBoundedChannelContextPropagation:
    """M27: BoundedChannel propagates contextvars from sender to receiver."""

    @pytest.mark.asyncio
    async def test_context_propagates_send_to_receive(self) -> None:
        """Items received carry the sender's context variables."""
        channel: BoundedChannel[str] = BoundedChannel(capacity=1)

        REQUEST_ID.set("req-sender-abc")
        await channel.send("hello")

        # Clear context on receiver side before receiving
        REQUEST_ID.set("req-receiver-xyz")
        await channel.receive()

        # After receive, the sender's context var value should be restored
        assert REQUEST_ID.get() == "req-sender-abc"

    @pytest.mark.asyncio
    async def test_send_nowait_propagates_context(self) -> None:
        """send_nowait() also captures the sender's context."""
        channel: BoundedChannel[int] = BoundedChannel(capacity=1)

        REQUEST_ID.set("sync-send-ctx")
        channel.send_nowait(42)

        REQUEST_ID.set("other-ctx")
        item = await channel.receive()

        assert item == 42
        assert REQUEST_ID.get() == "sync-send-ctx"

    @pytest.mark.asyncio
    async def test_receive_nowait_restores_context(self) -> None:
        """receive_nowait() restores the sender's context."""
        channel: BoundedChannel[str] = BoundedChannel(capacity=1)

        REQUEST_ID.set("nowait-sender")
        channel.send_nowait("data")

        REQUEST_ID.set("nowait-receiver")
        item = channel.receive_nowait()

        assert item == "data"
        assert REQUEST_ID.get() == "nowait-sender"

    @pytest.mark.asyncio
    async def test_each_item_independent_context(self) -> None:
        """Each item in the channel carries its own independent context snapshot."""
        channel: BoundedChannel[str] = BoundedChannel(capacity=10)

        REQUEST_ID.set("ctx-A")
        await channel.send("item-A")
        REQUEST_ID.set("ctx-B")
        await channel.send("item-B")

        await channel.receive()
        assert REQUEST_ID.get() == "ctx-A"

        await channel.receive()
        assert REQUEST_ID.get() == "ctx-B"

    @pytest.mark.asyncio
    async def test_item_value_unchanged(self) -> None:
        """The value itself is unchanged by context wrapping."""
        channel: BoundedChannel[dict] = BoundedChannel(capacity=1)
        payload = {"key": "value", "count": 42}
        await channel.send(payload)
        received = await channel.receive()
        assert received == payload
