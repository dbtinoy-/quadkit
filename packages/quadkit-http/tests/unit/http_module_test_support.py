"""Shared factories for HTTP module tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

def _make_raw_response(
    *,
    status: int = 200,
    body: bytes = b"",
    content_type: str = "text/plain",
    url: str = "http://example.com",
) -> MagicMock:
    """Build a minimal mock that matches what ``_to_http_response`` expects."""
    resp = MagicMock()
    resp.status = status
    resp.headers = {"Content-Type": content_type}
    resp.read = AsyncMock(return_value=body)
    resp.get_encoding = MagicMock(return_value="utf-8")
    resp.json = AsyncMock(return_value=None)
    resp.url = url
    return resp


def _make_mock_retry_policy() -> MagicMock:
    """Retry policy that executes the callable directly — no delay."""
    policy = MagicMock()

    async def execute(fn, method=None):  # type: ignore[no-untyped-def]
        return await fn()

    policy.execute = AsyncMock(side_effect=execute)
    return policy


