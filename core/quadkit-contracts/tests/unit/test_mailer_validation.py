"""Validation tests for EmailMessage (notification/webhook audit F1, D1)."""

from __future__ import annotations

import pytest

from quadkit.contracts.mailer import EmailMessage


class TestEmailMessageRejectsHeaderInjection:
    def test_subject_rejects_crlf(self) -> None:
        with pytest.raises(ValueError, match="subject"):
            EmailMessage(
                to=["victim@example.com"],
                subject="Hi\r\nBcc: attacker@evil.com",
            )

    def test_recipient_rejects_crlf(self) -> None:
        with pytest.raises(ValueError, match="to"):
            EmailMessage(
                to=["victim@example.com\r\nBcc: spy@evil.com"],
                subject="Hello",
            )

    def test_cc_rejects_crlf(self) -> None:
        with pytest.raises(ValueError, match="cc"):
            EmailMessage(
                to=["victim@example.com"],
                cc=["other@example.com\r\nBcc: spy@evil.com"],
                subject="Hello",
            )

    def test_from_name_rejects_crlf(self) -> None:
        with pytest.raises(ValueError, match="from_name"):
            EmailMessage(
                to=["victim@example.com"],
                subject="Hello",
                from_name="Admin\r\nBcc: spy@evil.com",
            )

    def test_header_value_rejects_crlf(self) -> None:
        with pytest.raises(ValueError, match="X-Custom"):
            EmailMessage(
                to=["victim@example.com"],
                subject="Hello",
                headers={"X-Custom": "ok\r\nInjected: bad"},
            )

    def test_header_name_must_be_rfc5322_token(self) -> None:
        with pytest.raises(ValueError, match="X-Evil"):
            EmailMessage(
                to=["victim@example.com"],
                subject="Hello",
                headers={"X-Evil: Injected": "bad"},
            )

    def test_body_and_html_body_may_contain_newlines(self) -> None:
        msg = EmailMessage(
            to=["victim@example.com"],
            subject="Hello",
            body="line one\nline two",
            html_body="<p>line one\nline two</p>",
        )
        assert msg.body == "line one\nline two"
        assert msg.html_body == "<p>line one\nline two</p>"

    def test_valid_message_still_constructs(self) -> None:
        msg = EmailMessage(
            to=["a@example.com", "b@example.com"],
            subject="OK",
            from_name="Admin",
            headers={"X-Custom": "value"},
        )
        assert msg.subject == "OK"
