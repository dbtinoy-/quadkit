"""Rate-limit diagnostics must not expose client or user identifiers."""

from importlib import import_module
from typing import NoReturn
from unittest.mock import MagicMock

import pytest
from starlette.requests import Request

from quadkit.contracts.exceptions import RateLimitError
from quadkit.web.middleware import rate_limit_strategies
from quadkit.web.middleware.rate_limit_strategies import RateLimiter

rate_limit_module = import_module("quadkit.web.middleware.rate_limit")


@pytest.mark.asyncio
async def test_rate_limit_logs_omit_user_id_and_client_ip(monkeypatch) -> None:
    user_id = "private-user-identifier-83d2"
    client_ip = "203.0.113.42"
    logger = MagicMock()
    monkeypatch.setattr(rate_limit_strategies, "logger", logger)

    request = Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/private/action",
            "raw_path": b"/private/action",
            "query_string": b"",
            "headers": [],
            "client": (client_ip, 12345),
            "server": ("example.test", 80),
            "state": {"user_id": user_id},
        },
    )
    limiter = RateLimiter()

    await limiter.check_rate_limit(
        request,
        max_requests=1,
        window_seconds=60,
        scope="user",
        namespace="privacy-test",
    )
    with pytest.raises(RateLimitError):
        await limiter.check_rate_limit(
            request,
            max_requests=1,
            window_seconds=60,
            scope="user",
            namespace="privacy-test",
        )

    calls = logger.mock_calls
    assert "rate_limit.check_passed" in [call.args[0] for call in calls if call.args]
    assert "security.rate_limit_exceeded" in [
        call.args[0] for call in calls if call.args
    ]
    rate_limit_events = [
        call
        for call in calls
        if call.args
        and call.args[0] in {"rate_limit.check_passed", "security.rate_limit_exceeded"}
    ]
    assert all("key" not in call.kwargs for call in rate_limit_events)
    logged = repr(calls)
    assert user_id not in logged
    assert client_ip not in logged


@pytest.mark.asyncio
async def test_limiter_resolution_logs_exception_type_only(monkeypatch) -> None:
    private_error = "credential=private-token at /srv/private/tenant-42"
    logger = MagicMock()
    monkeypatch.setattr(rate_limit_module, "logger", logger)

    class _PrivateContainer:
        def resolve(self, _service: object) -> NoReturn:
            raise RuntimeError(private_error)

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/private/action",
            "headers": [],
            "client": ("203.0.113.42", 12345),
            "state": {"container": _PrivateContainer()},
        },
    )

    resolved = await rate_limit_module._resolve_container_limiter(request)

    assert resolved is None
    logger.debug.assert_called_once_with(
        "rate_limit_container_resolution_miss",
        error_type="RuntimeError",
    )
    assert private_error not in repr(logger.mock_calls)
    logger.exception.assert_not_called()
