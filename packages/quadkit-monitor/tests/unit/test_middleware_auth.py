"""Unit tests for the shared middleware bearer-token auth helpers."""

from __future__ import annotations

import pytest

from quadkit.monitor.middleware.auth import (
    bearer_token_from_scope,
    is_authorized,
    send_unauthorized,
)


def test_bearer_token_extracted_from_headers() -> None:
    scope = {"headers": [(b"authorization", b"Bearer tok-123")]}
    assert bearer_token_from_scope(scope) == b"tok-123"


def test_bearer_token_scheme_is_case_insensitive() -> None:
    scope = {"headers": [(b"Authorization", b"bearer tok-123")]}
    assert bearer_token_from_scope(scope) == b"tok-123"


def test_bearer_token_missing_or_wrong_scheme_returns_none() -> None:
    assert bearer_token_from_scope({}) is None
    assert bearer_token_from_scope({"headers": []}) is None
    assert bearer_token_from_scope({"headers": [(b"x-token", b"tok")]}) is None
    assert bearer_token_from_scope({"headers": [(b"authorization", b"Basic dXNlcjpwYXNz")]}) is None
    assert bearer_token_from_scope({"headers": [(b"authorization", b"Bearer")]}) is None


def test_is_authorized_open_when_no_token_configured() -> None:
    assert is_authorized({}, None) is True


def test_is_authorized_with_matching_token() -> None:
    scope = {"headers": [(b"authorization", b"Bearer s3cret")]}
    assert is_authorized(scope, "s3cret") is True


def test_is_authorized_with_wrong_or_missing_token() -> None:
    scope = {"headers": [(b"authorization", b"Bearer nope")]}
    assert is_authorized(scope, "s3cret") is False
    assert is_authorized({}, "s3cret") is False


@pytest.mark.asyncio
async def test_send_unauthorized_sends_401_with_www_authenticate() -> None:
    sent: list = []

    async def send(message: dict) -> None:
        sent.append(message)

    await send_unauthorized(send)

    assert sent[0]["status"] == 401
    headers = dict(sent[0]["headers"])
    assert headers[b"www-authenticate"] == b"Bearer"
    assert headers[b"content-type"] == b"text/plain"
    assert sent[1]["body"] == b"Unauthorized"
