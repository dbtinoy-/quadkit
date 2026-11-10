"""Tests for the ConsoleMailer backend."""

from __future__ import annotations

import pytest

from quadkit.contracts.core import HealthStatus
from quadkit.contracts.mailer import EmailMessage
from quadkit.notification.mailer.console_mailer import ConsoleMailer


def _message(**kw: object) -> EmailMessage:
    kw.setdefault("to", ["a@b.c"])
    kw.setdefault("subject", "hi")
    kw.setdefault("body", "plain body")
    return EmailMessage(**kw)  # type: ignore[arg-type]


class TestSend:
    @pytest.mark.asyncio
    async def test_returns_ok_receipt(self) -> None:
        result = await ConsoleMailer().send(_message())
        assert result.is_ok()
        receipt = result.unwrap()
        assert receipt.backend == "console"
        assert receipt.channel == "email"
        assert receipt.provider_reference == "console"
        assert receipt.message_id.startswith("console-")

    @pytest.mark.asyncio
    async def test_message_ids_unique(self) -> None:
        m = ConsoleMailer()
        r1 = await m.send(_message())
        r2 = await m.send(_message())
        assert r1.unwrap().message_id != r2.unwrap().message_id

    @pytest.mark.asyncio
    async def test_accepts_empty_body(self) -> None:
        result = await ConsoleMailer().send(_message(body=""))
        assert result.is_ok()

    @pytest.mark.asyncio
    async def test_custom_log_level_accepted(self) -> None:
        m = ConsoleMailer(log_level="warning")
        assert m.log_level == "warning"
        assert (await m.send(_message())).is_ok()


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_always_healthy(self) -> None:
        hc = await ConsoleMailer().health_check()
        assert hc.status is HealthStatus.HEALTHY
        assert hc.component == "mailer.console"
        assert "available" in hc.message.lower()
