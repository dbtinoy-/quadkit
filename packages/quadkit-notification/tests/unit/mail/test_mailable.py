"""Tests for Mailable and its escape_html helper (audit F2, D3)."""

from __future__ import annotations

import pytest

from quadkit.contracts.mailer import EmailMessage
from quadkit.notification.mailer.mailable import Mailable, escape_html


class TestEscapeHtml:
    def test_escapes_special_characters(self) -> None:
        assert escape_html("<script>alert('x')</script>") == (
            "&lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt;"
        )

    def test_escapes_quotes(self) -> None:
        assert escape_html('say "hi"') == "say &quot;hi&quot;"

    def test_plain_text_unchanged(self) -> None:
        assert escape_html("plain text") == "plain text"


class TestMailableDocumentedPattern:
    def test_docstring_example_escapes_user_name(self) -> None:
        class WelcomeMail(Mailable):
            def __init__(self, user_name: str, user_email: str) -> None:
                self.user_name = user_name
                self.user_email = user_email

            def to_message(self) -> EmailMessage:
                return EmailMessage(
                    to=[self.user_email],
                    subject=f"Welcome, {self.user_name}!",
                    body=f"Hi {self.user_name}, welcome aboard.",
                    html_body=(
                        f"<p>Hi <b>{escape_html(self.user_name)}</b>, "
                        f"welcome aboard.</p>"
                    ),
                )

        msg = WelcomeMail("<b>evil</b>", "u@example.com").to_message()
        assert "<b>evil</b>" not in msg.html_body
        assert "&lt;b&gt;evil&lt;/b&gt;" in msg.html_body