"""Tests for SMTPMailer."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from quadkit.contracts.mailer import EmailMessage
from quadkit.contracts.mailer.types import Attachment
from quadkit.notification.mailer.smtp_mailer import SMTPMailer
from quadkit.notification.exceptions import SMTPMailerError


class TestSMTPMailer:
    @pytest.fixture
    def mailer(self) -> SMTPMailer:
        return SMTPMailer(
            host="smtp.example.com",
            port=587,
            username="user@example.com",
            password="secret",
            use_tls=True,
            from_email="noreply@example.com",
        )

    @pytest.fixture
    def message(self) -> EmailMessage:
        return EmailMessage(
            to=["recipient@example.com"],
            subject="Test Subject",
            body="Hello, world!",
        )

    @pytest.mark.asyncio
    async def test_send_returns_ok_on_success(
        self, mailer: SMTPMailer, message: EmailMessage
    ) -> None:
        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_smtp = MagicMock()
            mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
            mock_smtp.__exit__ = MagicMock(return_value=False)
            mock_smtp.sendmail = MagicMock()
            mock_smtp_cls.return_value = mock_smtp

            result = await mailer.send(message)

        assert result.is_ok()
        receipt = result.unwrap()
        assert receipt.channel == "email"
        assert receipt.backend == "smtp"

    @pytest.mark.asyncio
    async def test_send_returns_err_on_smtp_error(
        self, mailer: SMTPMailer, message: EmailMessage
    ) -> None:
        import smtplib

        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_smtp_cls.side_effect = smtplib.SMTPException("Connection refused")
            result = await mailer.send(message)

        assert result.is_err()
        assert isinstance(result.unwrap_err(), SMTPMailerError)

    @pytest.mark.asyncio
    async def test_health_check_returns_healthy(self, mailer: SMTPMailer) -> None:
        from quadkit.contracts.core import HealthStatus

        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_smtp = MagicMock()
            mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
            mock_smtp.__exit__ = MagicMock(return_value=False)
            mock_smtp_cls.return_value = mock_smtp

            result = await mailer.health_check()

        assert result.status == HealthStatus.HEALTHY


class TestSMTPAttachments:
    """An email that cannot carry a file cannot send an invoice."""

    @pytest.fixture
    def mailer(self) -> SMTPMailer:
        return SMTPMailer(host="smtp.example.com", port=587, from_email="noreply@example.com")

    @staticmethod
    def _pdf() -> Attachment:
        return Attachment(
            filename="INV-2026-0001.pdf",
            content=b"%PDF-1.4\nfake invoice bytes\n",
            content_type="application/pdf",
        )

    def test_a_message_without_attachments_is_still_a_plain_alternative(
        self, mailer: SMTPMailer
    ) -> None:
        """The common case must not grow a wrapper it does not need."""
        mime = mailer._build_mime(
            EmailMessage(to=["a@example.com"], subject="Hi", body="text", html_body="<p>text</p>")
        )

        assert mime.get_content_type() == "multipart/alternative"
        assert [part.get_content_type() for part in mime.get_payload()] == [
            "text/plain",
            "text/html",
        ]

    def test_an_attachment_makes_the_message_mixed_with_the_bodies_inside(
        self, mailer: SMTPMailer
    ) -> None:
        """`mixed` wrapping `alternative` is what keeps HTML a body.

        Attaching the PDF as a sibling of the two text parts makes some
        clients show the HTML as a second download instead of rendering
        it.
        """
        mime = mailer._build_mime(
            EmailMessage(
                to=["a@example.com"],
                subject="Invoice",
                body="text",
                html_body="<p>text</p>",
                attachments=[self._pdf()],
            )
        )

        assert mime.get_content_type() == "multipart/mixed"
        top = mime.get_payload()
        assert top[0].get_content_type() == "multipart/alternative"
        assert [part.get_content_type() for part in top[0].get_payload()] == [
            "text/plain",
            "text/html",
        ]
        assert top[1].get_content_type() == "application/pdf"

    def test_the_attachment_survives_the_transfer_encoding(self, mailer: SMTPMailer) -> None:
        """Base64 in, identical bytes out — or the PDF will not open."""
        attachment = self._pdf()
        mime = mailer._build_mime(
            EmailMessage(to=["a@example.com"], subject="Invoice", attachments=[attachment])
        )

        part = mime.get_payload()[1]
        assert part.get_payload(decode=True) == attachment.content
        assert part.get_filename() == "INV-2026-0001.pdf"
        assert part.get("Content-Disposition").startswith("attachment")

    def test_a_content_id_makes_it_inline_for_the_html_body(self, mailer: SMTPMailer) -> None:
        """A logo is referenced by the body, not downloaded beside it."""
        mime = mailer._build_mime(
            EmailMessage(
                to=["a@example.com"],
                subject="Invoice",
                html_body='<img src="cid:logo">',
                attachments=[
                    Attachment(
                        filename="logo.png",
                        content=b"\x89PNG\r\n",
                        content_type="image/png",
                        content_id="logo",
                    )
                ],
            )
        )

        part = mime.get_payload()[1]
        assert part.get("Content-ID") == "<logo>"
        assert part.get("Content-Disposition").startswith("inline")

    def test_an_attachment_filename_cannot_smuggle_a_header(self) -> None:
        """It lands in Content-Disposition, so it is header-bound too."""
        with pytest.raises(ValueError, match="attachments"):
            EmailMessage(
                to=["a@example.com"],
                subject="Invoice",
                attachments=[Attachment(filename="in\r\nBcc: victim@example.com", content=b"")],
            )
