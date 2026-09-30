"""Tests for the S3 upload mixin: single-part and multipart upload paths."""

from __future__ import annotations

import base64
import hashlib

import pytest

from quadkit.contracts.infra.storage import UploadOptions
from quadkit.storage.backends._s3_upload_mixin import _S3UploadMixin
from quadkit.storage.exceptions import StorageError


class _FakeS3:
    """Records S3 calls and returns scripted responses."""

    def __init__(self, fail_on: str | None = None) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.upload_id = "UP-123"
        self.fail_on = fail_on

    async def put_object(self, **params) -> dict:
        self.calls.append(("put_object", params))
        return {"ETag": '"single"'}

    def create_multipart_upload(self, **params) -> dict:
        self.calls.append(("create_multipart_upload", params))
        return {"UploadId": self.upload_id}

    def upload_part(self, **params) -> dict:
        self.calls.append(("upload_part", params))
        return {"ETag": f'"{params["PartNumber"]}"'}

    def complete_multipart_upload(self, **params) -> dict:
        self.calls.append(("complete_multipart_upload", params))
        return {"ETag": '"multi"'}

    def abort_multipart_upload(self, **params) -> None:
        self.calls.append(("abort_multipart_upload", params))

    def names(self) -> list[str]:
        return [c[0] for c in self.calls]


class _Host(_S3UploadMixin):
    def __init__(
        self,
        client: _FakeS3,
        *,
        threshold: int = 100,
        chunk_size: int = 64,
        bucket: str = "bkt",
    ) -> None:
        self.bucket = bucket
        self.multipart_threshold = threshold
        self.multipart_chunk_size = chunk_size
        self._client = client

    async def _get_client(self) -> _FakeS3:
        return self._client

    def _build_sse_params(self) -> dict:
        return {}

    def _normalize_path(self, path: str) -> str:
        return path.lstrip("/")

    async def _get_file_size(self, data) -> int:
        if isinstance(data, (bytes, str)):
            return len(data.encode("utf-8") if isinstance(data, str) else data)
        if hasattr(data, "read"):
            return 0  # force small path for file-like doubles
        return 999_999

    def _normalize_upload_options(self, content_type, options) -> UploadOptions:
        if isinstance(content_type, UploadOptions):
            return content_type
        return UploadOptions(content_type=content_type, **options)


def _host(**kw) -> tuple[_Host, _FakeS3]:
    client = _FakeS3(**dict(kw.pop("client_kwargs", {})))
    return _Host(client, **kw), client


class TestSmallFile:
    async def test_bytes_upload(self) -> None:
        host, client = _host()
        info = await host._upload_small_file("dir/a.txt", b"hello")
        assert info.path == "dir/a.txt"
        assert info.size == 5
        assert info.etag == '"single"'
        assert client.names() == ["put_object"]
        params = client.calls[0][1]
        assert params["Bucket"] == "bkt"
        assert params["Key"] == "dir/a.txt"
        assert params["Body"] == b"hello"

    async def test_str_encoded(self) -> None:
        host, client = _host()
        await host._upload_small_file("a.txt", "héllo")
        assert client.calls[0][1]["Body"] == "héllo".encode()

    async def test_file_like_object(self) -> None:
        host, client = _host()

        class _File:
            def read(self) -> bytes:
                return b"filedata"

        await host._upload_small_file("a.bin", _File())
        assert client.calls[0][1]["Body"] == b"filedata"

    async def test_async_iterable(self) -> None:
        host, client = _host()

        async def gen():
            yield b"part1"
            yield "part2"

        await host._upload_small_file("a.bin", gen())
        assert client.calls[0][1]["Body"] == b"part1part2"

    async def test_unsupported_type(self) -> None:
        host, _client = _host()
        with pytest.raises(ValueError, match="Unsupported data type"):
            await host._upload_small_file("a", 12345)

    async def test_content_type_from_extension(self) -> None:
        host, client = _host()
        await host._upload_small_file("a.png", b"x")
        assert client.calls[0][1]["ContentType"] == "image/png"

    async def test_options_content_type_wins(self) -> None:
        host, client = _host()
        opt = UploadOptions(content_type="application/octet-stream")
        await host._upload_small_file("a.bin", b"x", opt)
        assert client.calls[0][1]["ContentType"] == "application/octet-stream"

    async def test_metadata_and_acl(self) -> None:
        host, client = _host()
        opt = UploadOptions(metadata={"Owner": "me"}, public=True)
        await host._upload_small_file("a", b"x", opt)
        params = client.calls[0][1]
        assert params["Metadata"] == {"owner": "me"}  # lowercased by model
        assert params["ACL"] == "public-read"

    async def test_metadata_on_info(self) -> None:
        host, _ = _host()
        opt = UploadOptions(metadata={"k": "v"})
        info = await host._upload_small_file("a", b"x", opt)
        assert info.metadata == {"k": "v"}


class TestMultipart:
    async def test_bytes_chunked(self) -> None:
        host, client = _host(threshold=10, chunk_size=4)
        info = await host._upload_large_file("big.bin", b"0123456789")
        assert info.size == 10
        assert info.etag == '"multi"'
        parts = [c for c in client.calls if c[0] == "upload_part"]
        assert len(parts) == 3  # 4 + 4 + 2
        assert [p[1]["PartNumber"] for p in parts] == [1, 2, 3]
        assert client.names() == [
            "create_multipart_upload",
            "upload_part",
            "upload_part",
            "upload_part",
            "complete_multipart_upload",
        ]

    async def test_chunk_checksums(self) -> None:
        host, client = _host(threshold=10, chunk_size=4)
        await host._upload_large_file("big.bin", b"0123456789")
        part = client.calls[1][1]
        expected = base64.b64encode(hashlib.sha256(b"0123").digest()).decode()
        assert part["ChecksumSHA256"] == expected

    async def test_str_content(self) -> None:
        host, _client = _host(threshold=10, chunk_size=4)
        info = await host._upload_large_file("big.txt", "hello world")
        assert info.size == 11

    async def test_file_like_chunks(self) -> None:
        host, client = _host(threshold=10, chunk_size=4)

        class _File:
            def __init__(self) -> None:
                self.data = b"abcdefghij"
                self.pos = 0

            def read(self, n: int) -> bytes:
                chunk = self.data[self.pos : self.pos + n]
                self.pos += n
                return chunk

        info = await host._upload_large_file("big.bin", _File())
        assert info.size == 10
        parts = [c for c in client.calls if c[0] == "upload_part"]
        assert len(parts) == 3

    async def test_async_iterable_chunks(self) -> None:
        host, client = _host(threshold=10, chunk_size=4)

        async def gen():
            yield b"abcd"
            yield "efgh"
            yield b"ij"

        info = await host._upload_large_file("big.bin", gen())
        assert info.size == 10
        parts = [c for c in client.calls if c[0] == "upload_part"]
        assert [p[1]["Body"] for p in parts] == [b"abcd", b"efgh", b"ij"]

    async def test_unsupported_type_aborts(self) -> None:
        pytest.importorskip("botocore")
        host, client = _host(threshold=10, chunk_size=4)
        with pytest.raises(StorageError, match="Multipart upload failed"):
            await host._upload_large_file("big", 42)
        assert "abort_multipart_upload" in client.names()

    async def test_error_mid_upload_aborts_and_raises(self) -> None:
        pytest.importorskip("botocore")
        client = _FakeS3()

        def bad_upload_part(**params) -> dict:
            client.calls.append(("upload_part", params))
            raise RuntimeError("network blip")

        client.upload_part = bad_upload_part  # type: ignore[method-assign]
        host = _Host(client, threshold=10, chunk_size=4)
        with pytest.raises(StorageError, match="Multipart upload failed"):
            await host._upload_large_file("big.bin", b"0123456789")
        assert "abort_multipart_upload" in client.names()
        assert "complete_multipart_upload" not in client.names()

    async def test_create_failure_no_abort(self) -> None:
        pytest.importorskip("botocore")
        client = _FakeS3()

        def bad_create(**params) -> dict:
            client.calls.append(("create_multipart_upload", params))
            raise RuntimeError("no permission")

        client.create_multipart_upload = bad_create  # type: ignore[method-assign]
        host = _Host(client, threshold=10, chunk_size=4)
        with pytest.raises(StorageError, match="Multipart upload failed"):
            await host._upload_large_file("big.bin", b"0123456789")
        assert "abort_multipart_upload" not in client.names()

    async def test_content_type_and_acl_on_create(self) -> None:
        host, client = _host(threshold=10, chunk_size=4)
        opt = UploadOptions(content_type="video/mp4", public=True)
        await host._upload_large_file("m.mp4", b"x" * 20, opt)
        create = client.calls[0][1]
        assert create["ContentType"] == "video/mp4"
        assert create["ACL"] == "public-read"

    async def test_complete_receives_all_parts(self) -> None:
        host, client = _host(threshold=10, chunk_size=4)
        await host._upload_large_file("big.bin", b"0123456789")
        complete = client.calls[-1]
        assert complete[0] == "complete_multipart_upload"
        assert complete[1]["UploadId"] == "UP-123"
        assert len(complete[1]["MultipartUpload"]["Parts"]) == 3


class TestUploadDispatch:
    async def test_small_goes_single(self) -> None:
        host, client = _host(threshold=100)
        await host.upload("a.txt", b"tiny")
        assert client.names() == ["put_object"]

    async def test_large_goes_multipart(self) -> None:
        host, client = _host(threshold=4, chunk_size=4)

        async def _size(data) -> int:
            return 100

        host._get_file_size = _size  # type: ignore[method-assign]
        await host.upload("big.txt", b"x" * 100)
        assert "create_multipart_upload" in client.names()
        assert "put_object" not in client.names()

    async def test_normalizes_path(self) -> None:
        host, client = _host(threshold=100)
        await host.upload("/leading/slash.txt", b"tiny")
        assert client.calls[0][1]["Key"] == "leading/slash.txt"

    async def test_options_passthrough(self) -> None:
        host, client = _host(threshold=100)
        await host.upload("a.txt", b"tiny", content_type="text/plain", metadata={"a": "b"})
        params = client.calls[0][1]
        assert params["ContentType"] == "text/plain"
        assert params["Metadata"] == {"a": "b"}
