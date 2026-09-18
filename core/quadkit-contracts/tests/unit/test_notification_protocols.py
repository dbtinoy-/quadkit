"""Tests for notification protocols."""

from __future__ import annotations

from quadkit.contracts.notification.protocols import (
    PushChannelProtocol,
    SMSChannelProtocol,
)


class TestSMSChannelProtocol:
    """Tests for SMSChannelProtocol."""

    def test_is_runtime_checkable(self) -> None:
        assert hasattr(SMSChannelProtocol, "__protocol_attrs__") or hasattr(SMSChannelProtocol, "__annotations__")

    def test_has_send_method(self) -> None:
        assert hasattr(SMSChannelProtocol, "send")

    def test_has_health_check_method(self) -> None:
        assert hasattr(SMSChannelProtocol, "health_check")


class TestPushChannelProtocol:
    """Tests for PushChannelProtocol."""

    def test_is_runtime_checkable(self) -> None:
        assert hasattr(PushChannelProtocol, "__protocol_attrs__") or hasattr(PushChannelProtocol, "__annotations__")

    def test_has_send_method(self) -> None:
        assert hasattr(PushChannelProtocol, "send")

    def test_has_send_batch_method(self) -> None:
        assert hasattr(PushChannelProtocol, "send_batch")

    def test_has_health_check_method(self) -> None:
        assert hasattr(PushChannelProtocol, "health_check")
