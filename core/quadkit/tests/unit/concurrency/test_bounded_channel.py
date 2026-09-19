"""Tests for BoundedChannel - comprehensive tests for channel operations."""

import asyncio

import pytest

from quadkit.concurrency.channels.channel import BoundedChannel
from quadkit.concurrency.exceptions import ChannelClosedError, ChannelFullError


@pytest.fixture(autouse=True)
def _reset_channel_default_capacity() -> None:
    """Isolate tests from BoundedChannel.configure() (e.g. booted providers)."""
    previous = BoundedChannel._default_capacity
    BoundedChannel._default_capacity = 0
    yield
    BoundedChannel._default_capacity = previous


class TestBoundedChannelInit:
    """Tests for BoundedChannel initialization."""

    def test_init_unbounded(self) -> None:
        """Test initialization with default (unbounded) capacity."""
        channel = BoundedChannel()
        assert channel.capacity == 0
        assert channel.is_empty is True
        assert channel.is_full is False

    def test_init_bounded(self) -> None:
        """Test initialization with bounded capacity."""
        channel = BoundedChannel(capacity=10)
        assert channel.capacity == 10

    def test_init_zero_capacity(self) -> None:
        """Test initialization with zero capacity."""
        channel = BoundedChannel(capacity=0)
        assert channel.capacity == 0

    def test_is_closed_initially_false(self) -> None:
        """Test that channel is not closed initially."""
        channel = BoundedChannel(capacity=1)
        assert channel.is_closed is False


class TestBoundedChannelSendReceive:
    """Tests for basic send and receive operations."""

    @pytest.mark.asyncio
    async def test_send_and_receive(self) -> None:
        """Test basic send and receive."""
        channel = BoundedChannel[str](capacity=1)
        await channel.send("hello")
        assert channel.size == 1
        result = await channel.receive()
        assert result == "hello"
        assert channel.is_empty

    @pytest.mark.asyncio
    async def test_send_multiple_items(self) -> None:
        """Test sending and receiving multiple items."""
        channel = BoundedChannel[int](capacity=5)
        for i in range(5):
            await channel.send(i)
        assert channel.size == 5

        for i in range(5):
            assert await channel.receive() == i

    @pytest.mark.asyncio
    async def test_send_nowait_and_receive_nowait(self) -> None:
        """Test non-blocking send and receive."""
        channel = BoundedChannel[str](capacity=2)
        channel.send_nowait("first")
        channel.send_nowait("second")

        assert channel.receive_nowait() == "first"
        assert channel.receive_nowait() == "second"


class TestBoundedChannelClose:
    """Tests for channel close operations."""

    @pytest.mark.asyncio
    async def test_close_channel(self) -> None:
        """Test closing a channel."""
        channel = BoundedChannel[str](capacity=1)
        await channel.send("item")
        await channel.close()
        assert channel.is_closed is True

    @pytest.mark.asyncio
    async def test_send_to_closed_raises(self) -> None:
        """Test that sending to a closed channel raises."""
        channel = BoundedChannel[str](capacity=1)
        await channel.close()

        with pytest.raises(ChannelClosedError):
            await channel.send("item")

    @pytest.mark.asyncio
    async def test_send_nowait_to_closed_raises(self) -> None:
        """Test that send_nowait to closed channel raises."""
        channel = BoundedChannel[str](capacity=1)
        await channel.close()

        with pytest.raises(ChannelClosedError):
            channel.send_nowait("item")


class TestBoundedChannelBackpressure:
    """Tests for backpressure with bounded channels."""

    @pytest.mark.asyncio
    async def test_send_nowait_raises_when_full(self) -> None:
        """Test that send_nowait raises when channel is full."""
        channel = BoundedChannel[int](capacity=1)
        channel.send_nowait(1)

        with pytest.raises(ChannelFullError):
            channel.send_nowait(2)

    @pytest.mark.asyncio
    async def test_send_nowait_raises_when_full(self) -> None:
        """Test that send_nowait raises when channel is full."""
        channel = BoundedChannel[int](capacity=1)
        channel.send_nowait(1)

        with pytest.raises(ChannelFullError):
            channel.send_nowait(2)


class TestBoundedChannelSize:
    """Tests for channel size properties."""

    @pytest.mark.asyncio
    async def test_size_empty(self) -> None:
        """Test size of empty channel."""
        channel = BoundedChannel[str](capacity=5)
        assert channel.size == 0

    @pytest.mark.asyncio
    async def test_size_after_send(self) -> None:
        """Test size after sending items."""
        channel = BoundedChannel[str](capacity=5)
        await channel.send("a")
        await channel.send("b")
        assert channel.size == 2

    @pytest.mark.asyncio
    async def test_size_after_receive(self) -> None:
        """Test size after receiving items."""
        channel = BoundedChannel[str](capacity=5)
        await channel.send("a")
        await channel.send("b")
        await channel.receive()
        assert channel.size == 1

    @pytest.mark.asyncio
    async def test_is_empty(self) -> None:
        """Test is_empty property."""
        channel = BoundedChannel[str](capacity=1)
        assert channel.is_empty is True
        await channel.send("item")
        assert channel.is_empty is False
        await channel.receive()
        assert channel.is_empty is True

    @pytest.mark.asyncio
    async def test_is_full(self) -> None:
        """Test is_full property."""
        channel = BoundedChannel[str](capacity=1)
        assert channel.is_full is False
        await channel.send("item")
        assert channel.is_full is True


class TestChannelExceptions:
    """Tests for channel exceptions."""

    def test_channel_full_error(self) -> None:
        """Test ChannelFullError properties."""
        error = ChannelFullError("full", capacity=5)
        assert error.capacity == 5
        assert "full" in str(error)

    def test_channel_closed_error(self) -> None:
        """Test ChannelClosedError properties."""
        error = ChannelClosedError("closed")
        assert "closed" in str(error)


class TestBoundedChannelConfigure:
    """BoundedChannel.configure() sets the default for capacity-omitted channels."""

    def test_configure_changes_default_only_for_omitted_capacity(self) -> None:
        BoundedChannel.configure(7)
        try:
            assert BoundedChannel().capacity == 7
            assert BoundedChannel(capacity=0).capacity == 0  # explicit 0 = unbounded
            assert BoundedChannel(capacity=3).capacity == 3
        finally:
            BoundedChannel.configure(0)
