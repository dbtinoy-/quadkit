"""Shared fakes for the integration test modules.

The probes, cleanup and fixture suites all stand up local stand-ins for the
services they talk to: a one-shot awaitable, an async context manager, a TCP
listener and a minimal HTTP 200 server. They live here so each suite module
stays focused on its own subject and under the file-size limit.
"""

from __future__ import annotations

import asyncio
from typing import Any

__all__ = ["_AC", "_AsyncCM", "_HTTP200", "_TCP"]


class _TCP:
    def __init__(self) -> None:
        self.server: asyncio.AbstractServer | None = None
        self.port = 0

    async def start(self) -> int:
        async def _handler(reader: Any, writer: Any) -> None:
            writer.close()
            await writer.wait_closed()

        self.server = await asyncio.start_server(_handler, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]
        return self.port

    async def stop(self) -> None:
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()


class _HTTP200:
    def __init__(self) -> None:
        self.server: asyncio.AbstractServer | None = None
        self.port = 0

    async def start(self) -> int:
        async def _handler(reader: Any, writer: Any) -> None:
            while True:
                line = await reader.readline()
                if line in (b"\r\n", b"\n", b""):
                    break
            writer.write(
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: application/json\r\n"
                b"Content-Length: 2\r\n\r\n{}"
            )
            await writer.drain()
            writer.close()
            await writer.wait_closed()

        self.server = await asyncio.start_server(_handler, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]
        return self.port

    async def stop(self) -> None:
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()


class _AsyncCM:
    def __init__(self, value: Any) -> None:
        self._value = value

    async def __aenter__(self) -> Any:
        return self._value

    async def __aexit__(self, *exc: object) -> bool:
        return False


class _AC:
    """One-shot awaitable returning *value*."""

    def __init__(self, value: Any) -> None:
        self._value = value

    def __await__(self) -> Any:
        async def _get() -> Any:
            return self._value

        return _get().__await__()
