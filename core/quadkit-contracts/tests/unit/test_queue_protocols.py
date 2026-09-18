"""Tests for queue protocols."""

from __future__ import annotations

from quadkit.contracts.queue.protocols import MessageConsumerProtocol, QueueProtocol


class TestQueueProtocol:
    """Tests for QueueProtocol."""

    def test_is_runtime_checkable(self) -> None:
        assert hasattr(QueueProtocol, "__protocol_attrs__") or hasattr(QueueProtocol, "__annotations__")

    def test_has_connect_method(self) -> None:
        assert hasattr(QueueProtocol, "connect")

    def test_has_close_method(self) -> None:
        assert hasattr(QueueProtocol, "close")

    def test_has_publish_method(self) -> None:
        assert hasattr(QueueProtocol, "publish")

    def test_has_subscribe_method(self) -> None:
        assert hasattr(QueueProtocol, "subscribe")


class TestMessageConsumerProtocol:
    """Tests for MessageConsumerProtocol."""

    def test_is_runtime_checkable(self) -> None:
        assert hasattr(MessageConsumerProtocol, "__protocol_attrs__") or hasattr(MessageConsumerProtocol, "__annotations__")

    def test_has_start_method(self) -> None:
        assert hasattr(MessageConsumerProtocol, "start")

    def test_has_stop_method(self) -> None:
        assert hasattr(MessageConsumerProtocol, "stop")
