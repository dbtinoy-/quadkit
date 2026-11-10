"""SMTP header-injection handling (notification/webhook audit F1, D2).

D1 (contracts) makes CR/LF messages impossible to construct; these tests
prove the backend still fails closed and returns Err if a message is
tampered past the boundary (defense-in-depth).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from email.errors import HeaderParseError

from quadkit.contracts.mailer import EmailMessage
from quadkit.notification.exceptions import SMTPMailerError
from quadkit.notification.mailer.smtp_mailer import SMTPMailer


class TestStdlibHeaderInjectionBarrier:
    def test_stdlib_raises_on_embedded_header(self) -> None:
        """Evidence test: compat32 stores CRLF but as_string() rejects it.

        Locks in the audit correction (spec §2.1.3): the injection is
        blocked by stdlib at serialization on all supported interpreters.
        """
        from email.mime.multipart import MIMEMultipart

        mime = MIMEMultipart("alternative")
        mime["Subject"] = "Hi there\r\nBcc: attacker@evil.com"
        with pytest.raises(HeaderParseError, match="embedded header"):
            mime.as_string()


class TestSMTPMailerFailsClosedOnInjectedMessage:
    @pytest.fixture
    def mailer(self) -> SMTPMailer:
        return SMTPMailer(host="smtp.example.com", port=587, from_email="noreply@example.com")

    async def _tampered_message(self) -> EmailMessage:
        message = EmailMessage(to=["victim@example.com"], subject="Hello")
        # Bypass D1's __post_init__ check to prove the backend shim
        # independently (a message that predates validation, or was
        # mutated past the frozen boundary).
        object.__setattr__(message, "subject", "Hello\r\nBcc: attacker@evil.com")
        return message

    @pytest.mark.asyncio
    async def test_send_returns_err_not_raise(self, mailer: SMTPMailer) -> None:
        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_smtp = MagicMock()
            mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
            mock_smtp.__exit__ = MagicMock(return_value=False)
            mock_smtp.sendmail = MagicMock()
            mock_smtp_cls.return_value = mock_smtp

            result = await mailer.send(await self._tampered_message())

        assert result.is_err()
        assert isinstance(result.unwrap_err(), SMTPMailerError)
        mock_smtp.sendmail.assert_not_called()

    @pytest.mark.asyncio
    async def test_build_mime_serialization_raises_header_parse_error(
        self, mailer: SMTPMailer
    ) -> None:
        mime = mailer._build_mime(await self._tampered_message())
        with pytest.raises(HeaderParseError):
            mime.as_string()