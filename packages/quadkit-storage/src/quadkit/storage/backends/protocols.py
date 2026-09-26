"""Lightweight Protocols for storage driver typing (tests + mypy helpers)."""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class StreamingBodyProtocol(
    Protocol,
    AbstractAsyncContextManager["StreamingBodyProtocol"],
):
    """Protocol representing streaming body returned by some S3 clients."""

    async def read(self, n: int | None = None) -> bytes: ...


class _S3ClientProtocol(Protocol):  # noqa: PYI046
    """Minimal S3 client protocol used by our S3Driver.

    This keeps mypy happy without depending on `aiobotocore` types.
    """

    async def put_object(self, **kwargs: Any) -> dict[str, Any]: ...

    async def create_multipart_upload(self, **kwargs: Any) -> dict[str, Any]: ...

    async def upload_part(self, **kwargs: Any) -> dict[str, Any]: ...

    async def complete_multipart_upload(self, **kwargs: Any) -> dict[str, Any]: ...

    async def abort_multipart_upload(self, **kwargs: Any) -> dict[str, Any]: ...

    async def get_object(self, **kwargs: Any) -> dict[str, Any]: ...

    async def delete_object(self, **kwargs: Any) -> dict[str, Any]: ...

    async def head_object(self, **kwargs: Any) -> dict[str, Any]: ...

    def get_paginator(self, name: str) -> Any: ...

    async def generate_presigned_url(self, *args: Any, **kwargs: Any) -> str: ...
