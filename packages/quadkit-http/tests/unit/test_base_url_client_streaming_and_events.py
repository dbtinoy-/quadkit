"""Tests for BaseURLHTTPClient, the streaming mixins (SSE / multipart /
raw chunks), the Result-returning verb paths, and the HTTP domain events.

All tests are fake-backed — no network I/O.
"""

from __future__ import annotations

import contextlib
from typing import Any

import pytest
from quadkit.contracts.web import HttpResponse
from quadkit.contracts.web.sse import ServerSentEvent
from quadkit.http.client import base_url_client as base_url_client_module
from quadkit.http.client._streaming import _HTTPStreamingMixin
from quadkit.http.client._verbs import _HTTPVerbsMixin
from quadkit.http.exceptions import (
    HTTPConnectionError,
    HTTPStatusError,
    HTTPTimeoutError,
)
from quadkit.http.client.base_url_client import BaseURLHTTPClient, StreamContext
from quadkit.http.events import (
    RequestCompletedEvent,
    RequestRetryExhaustedEvent,
    RequestTimeoutEvent,
)
from quadkit.result import Err, Ok


# ── Fakes ─────────────────────────────────────────────────────────────────


class _FakePool:
    def __init__(self) -> None:
        self.session: Any = _FakeAiohttpSession()


class _FakeAiohttpResponse:
    def __init__(self, lines: list[bytes], status: int = 200) -> None:
        self._lines = lines
        self.status = status
        self.method = "GET"
        self.url = "https://api.test/x"

    @property
    def content(self) -> Any:
        lines = self._lines

        class _Content:
            def __aiter__(self) -> Any:
                async def _gen() -> Any:
                    for line in lines:
                        yield line

                return _gen()

            def iter_chunks(self) -> Any:
                async def _chunks() -> Any:
                    for line in lines:
                        yield (line, False)

                return _chunks()

        return _Content()


class _FakeAiohttpSession:
    def __init__(self) -> None:
        self.response: _FakeAiohttpResponse | None = None
        self.requests: list[tuple[Any, ...]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> Any:
        self.requests.append((method, url, kwargs))

        @contextlib.asynccontextmanager
        async def _cm() -> Any:
            if self.response is not None:
                yield self.response
            else:
                raise AssertionError("no fake response configured")

        return _cm()


class _FakeHTTPClient:
    """Stands in for HTTPClient inside BaseURLHTTPClient."""

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.started = False
        self.stopped = False
        self.calls: list[tuple[Any, ...]] = []
        self.response = HttpResponse(status=200, url="https://api.test/x", method="GET")
        self._pool = _FakePool()

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    async def request(self, method: str, url: str, **kwargs: Any) -> HttpResponse:
        self.calls.append((method, url, kwargs))
        return self.response

    async def _assert_url_safe(self, url: str) -> None:
        assert "://" in url


@pytest.fixture
def fake_http_client(monkeypatch: Any) -> _FakeHTTPClient:
    instance = _FakeHTTPClient()

    def _factory(**kwargs: Any) -> _FakeHTTPClient:
        instance.kwargs.update(kwargs)
        return instance

    monkeypatch.setattr(base_url_client_module, "HTTPClient", _factory)
    return instance


# ── HTTP domain events ────────────────────────────────────────────────────


def test_http_events_carry_payload_and_domain_defaults() -> None:
    retry = RequestRetryExhaustedEvent(url="https://x/y", method="GET", attempt_count=3)
    timeout = RequestTimeoutEvent(url="https://x/y", method="POST", timeout_seconds=30.0)
    completed = RequestCompletedEvent(url="https://x/y", method="GET", status_code=200)

    assert retry.url == "https://x/y" and retry.method == "GET" and retry.attempt_count == 3
    assert timeout.timeout_seconds == 30.0
    assert completed.status_code == 200

    for event in (retry, timeout, completed):
        assert event.event_id is not None
        assert event.occurred_at is not None

    with pytest.raises(Exception):
        retry.url = "changed"  # frozen


# ── BaseURLHTTPClient ─────────────────────────────────────────────────────


def test_resolve_url_rules() -> None:
    client = BaseURLHTTPClient(base_url="https://api.test/v1/")

    assert client._resolve_url("") == "https://api.test/v1"  # noqa: SLF001
    assert client._resolve_url("users") == "https://api.test/v1/users"  # noqa: SLF001
    assert client._resolve_url("/users") == "https://api.test/v1/users"  # noqa: SLF001
    assert client._resolve_url("https://other.test/z") == "https://other.test/z"  # noqa: SLF001


def test_merge_headers_precedence() -> None:
    client = BaseURLHTTPClient(base_url="", headers={"A": "1", "B": "2"})
    merged = client._merge_headers({"B": "9", "C": "3"})  # noqa: SLF001
    assert merged == {"A": "1", "B": "9", "C": "3"}


async def test_get_joins_url_and_merges_headers(
    fake_http_client: _FakeHTTPClient,
) -> None:
    client = BaseURLHTTPClient(
        base_url="https://api.test/v1",
        headers={"Authorization": "Bearer t"},
    )
    resp = await client.get("users", headers={"X-Trace": "1"})

    method, url, kwargs = fake_http_client.calls[0]
    assert method == "GET"
    assert url == "https://api.test/v1/users"
    assert kwargs["headers"] == {"Authorization": "Bearer t", "X-Trace": "1"}
    assert resp is fake_http_client.response
    assert fake_http_client.started is True


async def test_post_data_conversion(
    fake_http_client: _FakeHTTPClient,
) -> None:
    client = BaseURLHTTPClient()

    await client.post("x", data={"a": 1})
    _, _, kwargs = fake_http_client.calls[0]
    assert kwargs.get("json") == {"a": 1} and "data" not in kwargs

    await client.post("x", data=b"raw-bytes")
    _, _, kwargs = fake_http_client.calls[1]
    assert kwargs.get("data") == b"raw-bytes" and "json" not in kwargs

    await client.post("x")
    _, _, kwargs = fake_http_client.calls[2]
    assert "json" not in kwargs and "data" not in kwargs


async def test_put_delete_patch_verbs(
    fake_http_client: _FakeHTTPClient,
) -> None:
    client = BaseURLHTTPClient()
    await client.put("x")
    await client.delete("x")
    await client.patch("x")
    assert [c[0] for c in fake_http_client.calls] == ["PUT", "DELETE", "PATCH"]


async def test_lazy_initialisation_and_close(
    fake_http_client: _FakeHTTPClient,
) -> None:
    client = BaseURLHTTPClient()

    assert client._client is None  # noqa: SLF001
    await client.get("a")
    await client.get("b")
    assert fake_http_client.started is True  # created once

    await client.close()
    assert fake_http_client.stopped is True
    assert client._client is None  # noqa: SLF001

    # close() is idempotent.
    await client.close()
    assert fake_http_client.stopped is True


async def test_context_manager_closes(fake_http_client: _FakeHTTPClient) -> None:
    async with BaseURLHTTPClient() as client:
        await client.get("a")
    assert fake_http_client.stopped is True


async def test_stream_yields_decoded_lines(
    fake_http_client: _FakeHTTPClient,
) -> None:
    lines = [b'data: {"n": 1}\n', b"event: done\r\n", b"data: tail\n"]
    fake_http_client._pool.session.response = _FakeAiohttpResponse(lines)  # noqa: SLF001

    client = BaseURLHTTPClient(base_url="https://api.test")
    async with client.stream("POST", "chat", json={"q": 1}) as resp:
        assert resp.status == 200
        got = [line async for line in resp.aiter_lines()]

    assert got == ['data: {"n": 1}', "event: done", "data: tail"]
    method, url, kwargs = fake_http_client._pool.session.requests[0]  # noqa: SLF001
    assert method == "POST"
    assert url == "https://api.test/chat"
    assert kwargs["json"] == {"q": 1}


async def test_stream_raises_when_pool_session_missing(
    fake_http_client: _FakeHTTPClient,
) -> None:
    fake_http_client._pool.session = None  # noqa: SLF001
    client = BaseURLHTTPClient()

    with pytest.raises(RuntimeError, match="session is None"):
        async with client.stream("GET", "x"):
            pass


def test_stream_context_raise_for_status() -> None:
    ok = _FakeAiohttpResponse([], status=200)
    StreamContext(ok).raise_for_status()  # no-op

    bad = _FakeAiohttpResponse([], status=503)
    with pytest.raises(Exception, match="HTTP 503"):
        StreamContext(bad).raise_for_status()


# ── _request_result verb paths (Result semantics + metrics) ───────────────


class _MetricsFake:
    def __init__(self) -> None:
        self.counters: list[tuple[str, dict[str, str]]] = []
        self.histogram_calls: list[tuple[str, float, dict[str, str]]] = []

    def increment(self, name: str, tags: dict[str, str] | None = None, **kw: Any) -> None:
        self.counters.append((name, tags or {}))

    def histogram(self, name: str, value: float, tags: dict[str, str] | None = None, **kw: Any) -> None:
        self.histogram_calls.append((name, value, tags or {}))


class _VerbHarness(_HTTPVerbsMixin):
    def __init__(self, outcome: Any, metrics: Any = None) -> None:
        self._outcome = outcome
        self._metrics = metrics

    async def request(self, method: str, url: str, **kwargs: Any) -> HttpResponse:
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome


async def test_request_result_ok() -> None:
    metrics = _MetricsFake()
    resp = HttpResponse(status=200, url="https://x", method="GET")
    result = await _VerbHarness(resp, metrics)._request_result("GET", "https://x")

    assert isinstance(result, Ok)
    assert result.unwrap() is resp
    assert any(tags.get("status") == "200" for _, tags in metrics.counters)
    assert len(metrics.histogram_calls) == 1


async def test_request_result_status_error() -> None:
    resp = HttpResponse(status=404, url="https://x", method="GET")
    result = await _VerbHarness(resp)._request_result("GET", "https://x")

    assert isinstance(result, Err)
    error = result.unwrap_err()
    assert isinstance(error, HTTPStatusError)
    assert error.status == 404


async def test_request_result_connection_error() -> None:
    exc = HTTPConnectionError("boom")
    result = await _VerbHarness(exc)._request_result("GET", "https://x")

    assert isinstance(result, Err)
    assert result.unwrap_err() is exc


async def test_request_result_timeout_error() -> None:
    exc = HTTPTimeoutError("slow")
    result = await _VerbHarness(exc)._request_result("GET", "https://x")

    assert isinstance(result, Err)
    assert result.unwrap_err() is exc


# ── Streaming mixins: multipart / SSE / raw chunks ────────────────────────


class _StreamingHarness(_HTTPStreamingMixin):
    def __init__(self, pool: Any) -> None:
        self._pool = pool
        self.captured: list[tuple[str, str, dict[str, Any]]] = []

    async def _assert_url_safe(self, url: str) -> None:
        pass

    async def request(self, method: str, url: str, **kwargs: Any) -> HttpResponse:
        self.captured.append((method, url, kwargs))
        return HttpResponse(status=200, url=url, method=method)

    async def _request_result(self, method: str, url: str, **kwargs: Any) -> Any:
        self.captured.append((method, url, kwargs))
        from quadkit.result import Ok as _Ok

        return _Ok(HttpResponse(status=200, url=url, method=method))


async def test_post_multipart_builds_form_data() -> None:
    session = _FakeAiohttpSession()
    pool = _FakePool()
    pool.session = session  # noqa: SLF001
    harness = _StreamingHarness(pool)

    result = await harness.post_multipart(
        "https://upload.test/f",
        fields={
            "text": "plain",
            "bin": b"\x00\x01",
            "file": ("report.pdf", b"%PDF", "application/pdf"),
        },
    )

    assert isinstance(result, Ok)
    method, url, kwargs = harness.captured[0]
    assert method == "POST" and url == "https://upload.test/f"
    form = kwargs["data"]
    fields = {fd[0]["name"]: fd for fd in form._fields}  # noqa: SLF001
    assert fields["text"][2] == "plain"
    assert fields["bin"][2] == b"\x00\x01"
    file_headers, file_options, file_value = fields["file"]
    assert file_headers["filename"] == "report.pdf"
    assert file_value == b"%PDF"
    assert file_options["Content-Type"] == "application/pdf"


async def test_sse_parses_events() -> None:
    wire = [
        b"data: first\n",
        b"\n",
        b"event: update\n",
        b"data: a\n",
        b"data: b\n",
        b"id: 42\n",
        b"\n",
        b"data: trailing\n",
        b"\n",  # blank line dispatches the final event
    ]
    session = _FakeAiohttpSession()
    session.response = _FakeAiohttpResponse(wire)  # noqa: SLF001
    pool = _FakePool()
    pool.session = session  # noqa: SLF001
    harness = _StreamingHarness(pool)

    async with harness.sse("https://sse.test/stream") as events:
        parsed = [event async for event in events]

    assert [e.data for e in parsed] == ["first", "a\nb", "trailing"]
    assert parsed[1].event == "update"
    assert parsed[1].event_id == "42"
    # No explicit event: line → parser defaults to "message" (SSE spec).
    assert parsed[0].event == "message"


async def test_stream_yields_raw_chunks() -> None:
    wire = [b"part1", b"", b"part2"]
    session = _FakeAiohttpSession()
    session.response = _FakeAiohttpResponse(wire)  # noqa: SLF001
    pool = _FakePool()
    pool.session = session  # noqa: SLF001
    harness = _StreamingHarness(pool)

    chunks: list[bytes] = []
    async with harness.stream("GET", "https://files.test/big.bin") as iterator:
        async for chunk in iterator:
            chunks.append(chunk)

    assert chunks == [b"part1", b"part2"]  # empty chunk skipped


async def test_stream_raises_when_not_started() -> None:
    class _EmptyPool:
        session = None

    harness = _StreamingHarness(_EmptyPool())
    with pytest.raises(HTTPConnectionError, match="not started"):
        async with harness.stream("GET", "https://x/y"):
            pass
