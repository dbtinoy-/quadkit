"""Tests for logging/redaction module."""

from unittest.mock import MagicMock

import pytest

from quadkit.contracts.core.logging import RedactorProtocol
from quadkit.logging.redaction import (
    DefaultRedactor,
    DelegatingRedactor,
    NoOpRedactor,
    _redactor_var,
    get_redactor,
    set_redactor,
)


@pytest.fixture(autouse=True)
def _reset_redactor_var() -> None:
    """Isolate the process-global ContextVar state per test."""
    token = _redactor_var.set(None)
    yield
    _redactor_var.reset(token)


class TestDefaultRedactor:
    """Tests for DefaultRedactor class."""

    def test_denylisted_top_level_key_masked(self) -> None:
        """Test top-level denylisted keys are masked."""
        redactor = DefaultRedactor()
        result = redactor.redact_dict({"password": "x", "user_id": 7})
        assert result == {"password": "<redacted>", "user_id": 7}

    def test_case_insensitive_masking(self) -> None:
        """Test denylist matching is case-insensitive."""
        redactor = DefaultRedactor()
        result = redactor.redact_dict({"API_KEY": "x", "Session_Token": "y"})
        assert result == {"API_KEY": "<redacted>", "Session_Token": "<redacted>"}

    def test_nested_dict_recursion(self) -> None:
        """Test nested dicts are recursed and masked at depth."""
        redactor = DefaultRedactor()
        result = redactor.redact_dict({"headers": {"authorization": "x"}})
        assert result == {"headers": {"authorization": "<redacted>"}}

    def test_nested_list_recursion(self) -> None:
        """Test nested lists are recursed and masked at depth."""
        redactor = DefaultRedactor()
        result = redactor.redact_dict({"items": [{"token": "y"}, "plain"]})
        assert result == {"items": [{"token": "<redacted>"}, "plain"]}

    def test_non_denylisted_fields_pass_through(self) -> None:
        """Test non-denylisted fields pass through unchanged."""
        redactor = DefaultRedactor()
        data = {"name": "alice", "email": "a@b.c"}
        assert redactor.redact_dict(data) == data

    def test_redact_value_non_container_unchanged(self) -> None:
        """Test redact_value passes non-container values through (Decision 2)."""
        redactor = DefaultRedactor()
        assert redactor.redact_value("hunter2") == "hunter2"
        assert redactor.redact_value(42) == 42
        assert redactor.redact_value(None) is None

    def test_redact_value_recurses_tuple(self) -> None:
        """Test redact_value recurses tuples."""
        redactor = DefaultRedactor()
        result = redactor.redact_value(({"secret": "s"}, 1))
        assert result == ({"secret": "<redacted>"}, 1)

    def test_satisfies_redactor_protocol(self) -> None:
        """Test DefaultRedactor structurally satisfies RedactorProtocol."""
        assert isinstance(DefaultRedactor(), RedactorProtocol)

    def test_custom_denylist(self) -> None:
        """Test a custom field_denylist overrides the default."""
        redactor = DefaultRedactor(field_denylist=("custom_field",))
        result = redactor.redact_dict({"custom_field": "x", "password": "y"})
        assert result == {"custom_field": "<redacted>", "password": "y"}


class TestNoOpRedactor:
    """Tests for NoOpRedactor class."""

    def test_redact_dict_passes_through(self) -> None:
        """Test redact_dict returns data unchanged."""
        redactor = NoOpRedactor()
        data = {"key": "value", "nested": {"inner": "data"}}
        result = redactor.redact_dict(data)
        assert result == data

    def test_redact_dict_empty_dict(self) -> None:
        """Test redact_dict with empty dict."""
        redactor = NoOpRedactor()
        result = redactor.redact_dict({})
        assert result == {}

    def test_redact_value_passes_through(self) -> None:
        """Test redact_value returns value unchanged."""
        redactor = NoOpRedactor()
        value = "sensitive password"
        result = redactor.redact_value(value)
        assert result == value

    def test_redact_value_none(self) -> None:
        """Test redact_value with None."""
        redactor = NoOpRedactor()
        result = redactor.redact_value(None)
        assert result is None

    def test_redact_value_list(self) -> None:
        """Test redact_value with list."""
        redactor = NoOpRedactor()
        value = [1, 2, 3]
        result = redactor.redact_value(value)
        assert result == value


class TestDelegatingRedactor:
    """Tests for DelegatingRedactor — tracks the active pipeline policy."""

    def test_delegates_to_active_redactor(self) -> None:
        """DelegatingRedactor follows the redactor installed by set_redactor."""
        active = DefaultRedactor()
        token = set_redactor(active)
        try:
            delegating = DelegatingRedactor()
            result = delegating.redact_dict({"password": "x"})
            assert result == {"password": "<redacted>"}
            assert delegating.redact_value("x") == "x"
        finally:
            _redactor_var.reset(token)

    def test_falls_back_to_noop_before_configure(self) -> None:
        """Before any redactor is installed, DelegatingRedactor is a no-op."""
        assert DelegatingRedactor().redact_dict({"password": "x"}) == {"password": "x"}


class TestGetRedactor:
    """Tests for get_redactor function."""

    def test_get_redactor_returns_noop_by_default(self) -> None:
        """Test get_redactor returns NoOpRedactor when no override."""
        redactor = get_redactor()
        assert isinstance(redactor, NoOpRedactor)

    def test_get_redactor_with_context_override(self) -> None:
        """Test get_redactor returns context override when set."""
        custom_redactor = MagicMock()
        custom_redactor.redact_dict = lambda d: d
        custom_redactor.redact_value = lambda v: v

        token = set_redactor(custom_redactor)
        try:
            redactor = get_redactor()
            assert redactor is custom_redactor
        finally:
            from quadkit.logging.redaction import _redactor_var

            _redactor_var.reset(token)

    def test_get_redactor_after_reset_returns_noop(self) -> None:
        """Test get_redactor returns NoOpRedactor after token reset."""
        custom_redactor = MagicMock()
        custom_redactor.redact_dict = lambda d: d
        custom_redactor.redact_value = lambda v: v

        from quadkit.logging.redaction import _redactor_var

        token = set_redactor(custom_redactor)
        _redactor_var.reset(token)

        redactor = get_redactor()
        assert isinstance(redactor, NoOpRedactor)


class TestSetRedactor:
    """Tests for set_redactor function."""

    def test_set_redactor_returns_token(self) -> None:
        """Test set_redactor returns a token."""
        custom_redactor = MagicMock()
        token = set_redactor(custom_redactor)

        # Token should be used for reset
        from quadkit.logging.redaction import _redactor_var

        _redactor_var.reset(token)

        assert token is not None


class TestModuleExports:
    """Tests for module exports."""

    def test_noop_redactor_exported(self) -> None:
        """Test NoOpRedactor is exported."""
        from quadkit.logging.redaction import NoOpRedactor

        assert NoOpRedactor is not None

    def test_get_redactor_exported(self) -> None:
        """Test get_redactor is exported."""
        from quadkit.logging.redaction import get_redactor

        assert callable(get_redactor)

    def test_set_redactor_exported(self) -> None:
        """Test set_redactor is exported."""
        from quadkit.logging.redaction import set_redactor

        assert callable(set_redactor)


class TestCookieAndBearerCoverage:
    """plans/09172026 H-02 — cookie/session and bearer material is masked.

    Walked against the actual matcher semantics: ``cookie`` variants and
    ``bearer`` were reachable by neither the exact denylist nor the
    segment matcher, and ``x-api-key`` escapes the trailing-``key`` rule
    because ``x`` is not an auth-flavored prefix.
    """

    @pytest.mark.parametrize(
        "key",
        [
            "cookie",
            "cookies",
            "Cookie",
            "Set-Cookie",
            "set_cookie",
            "session_cookie",
            "bearer",
            "Bearer",
            "bearer_token",
            "auth_bearer",
            "x-api-key",
            "X-API-Key",
            "x_api_key",
            "X_API_KEY",
        ],
    )
    def test_secret_bearing_keys_masked(self, key: str) -> None:
        redactor = DefaultRedactor()
        assert redactor.redact_dict({key: "material"}) == {key: "<redacted>"}

    @pytest.mark.parametrize(
        "key",
        [
            "cookie_count",
            "cookies_accepted",
            "token_count",
            "prompt_tokens",
            "monkey",
            "keyboard",
            "user_id",
        ],
    )
    def test_benign_lookalikes_flow(self, key: str) -> None:
        redactor = DefaultRedactor()
        assert redactor.redact_dict({key: 5}) == {key: 5}

    def test_nested_cookie_material_masked(self) -> None:
        redactor = DefaultRedactor()
        result = redactor.redact_value(
            {
                "request": {
                    "headers": {
                        "cookie": "session=abc123;",
                        "x-api-key": "sk-live-1",
                        "user_agent": "test",
                    }
                }
            }
        )
        headers = result["request"]["headers"]
        assert headers["cookie"] == "<redacted>"
        assert headers["x-api-key"] == "<redacted>"
        assert headers["user_agent"] == "test"
