"""Unit tests for notification constants."""

from __future__ import annotations

import pytest

from quadkit.notification import constants


class TestVersion:
    """Tests for version constant."""

    def test_version_is_string(self) -> None:
        assert isinstance(constants.__version__, str)

    def test_version_exists(self) -> None:
        assert constants.__version__ is not None


class TestEnvironmentConstants:
    """Tests for environment variable constants."""

    def test_env_prefix(self) -> None:
        assert constants.ENV_PREFIX == "QK_NOTIFICATION__"

    def test_env_nested_delimiter(self) -> None:
        assert constants.ENV_NESTED_DELIMITER == "__"


class TestTwilioConstants:
    """Tests for Twilio-related constants."""

    def test_twilio_api_base(self) -> None:
        assert constants.TWILIO_API_BASE == "https://api.twilio.com/2010-04-01"

    def test_fcm_send_url(self) -> None:
        assert constants.FCM_SEND_URL == "https://fcm.googleapis.com/fcm/send"

    def test_default_fcm_timeout(self) -> None:
        assert constants.DEFAULT_FCM_TIMEOUT == 30

    def test_default_twilio_timeout(self) -> None:
        assert constants.DEFAULT_TWILIO_TIMEOUT == 30


class TestAPNsConstants:
    """Tests for APNs constants."""

    def test_apns_base_url(self) -> None:
        assert constants.APNS_BASE_URL == "https://api.push.apple.com"

    def test_apns_sandbox_url(self) -> None:
        assert constants.APNS_SANDBOX_URL == "https://api.development.push.apple.com"

    def test_default_apns_timeout(self) -> None:
        assert constants.DEFAULT_APNS_TIMEOUT == 30


class TestMailerConstants:
    """Tests for mailer constants."""

    def test_default_from_email(self) -> None:
        assert constants.DEFAULT_FROM_EMAIL == "noreply@example.com"

    def test_default_smtp_port(self) -> None:
        assert constants.DEFAULT_SMTP_PORT == 587

    def test_default_smtp_timeout(self) -> None:
        assert constants.DEFAULT_SMTP_TIMEOUT == 30

    def test_default_sendgrid_timeout(self) -> None:
        assert constants.DEFAULT_SENDGRID_TIMEOUT == 30

    def test_sendgrid_api_url(self) -> None:
        assert constants.SENDGRID_API_URL == "https://api.sendgrid.com/v3/mail/send"


class TestInboxConstants:
    """Tests for inbox constants."""

    def test_max_inbox_page_size(self) -> None:
        assert constants.MAX_INBOX_PAGE_SIZE == 100

    def test_default_retention_days(self) -> None:
        assert constants.DEFAULT_RETENTION_DAYS == 90


class TestAllExports:
    """Tests that all constants are exported."""

    def test_all_list_exists(self) -> None:
        assert hasattr(constants, "__all__")

    def test_all_list_contains_expected(self) -> None:
        expected = [
            "APNS_BASE_URL",
            "APNS_SANDBOX_URL",
            "DEFAULT_APNS_TIMEOUT",
            "DEFAULT_FCM_TIMEOUT",
            "DEFAULT_FROM_EMAIL",
            "DEFAULT_RETENTION_DAYS",
            "DEFAULT_SENDGRID_TIMEOUT",
            "DEFAULT_SMTP_PORT",
            "DEFAULT_SMTP_TIMEOUT",
            "DEFAULT_TWILIO_TIMEOUT",
            "ENV_NESTED_DELIMITER",
            "ENV_PREFIX",
            "FCM_SEND_URL",
            "MAX_INBOX_PAGE_SIZE",
            "SENDGRID_API_URL",
            "TWILIO_API_BASE",
        ]
        for name in expected:
            assert name in constants.__all__

    def test_constants_are_correct_types(self) -> None:
        assert isinstance(constants.APNS_BASE_URL, str)
        assert isinstance(constants.DEFAULT_APNS_TIMEOUT, int)
        assert isinstance(constants.MAX_INBOX_PAGE_SIZE, int)
        assert isinstance(constants.DEFAULT_RETENTION_DAYS, int)