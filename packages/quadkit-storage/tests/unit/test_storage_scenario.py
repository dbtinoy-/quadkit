"""Scenario coverage for the storage driver layer.

* ``DriverRegistry`` selection logic: built-in factories, required
  configuration per driver, custom driver registration,
* the real ``MemoryDriver`` and ``LocalDriver`` full-protocol
  round-trips (upload/download/info/list/delete/copy/move, traversal
  protection, presign/health semantics),
* the ``S3Driver`` logic with an injected fake S3 client: upload
  parameter mapping, download body handling, exists/info error
  mapping (NoSuchKey/NotFound vs. other ClientErrors), presigned
  URLs, public/endpoint URL construction, and key sanitization.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import botocore
import botocore.exceptions
from botocore.exceptions import ClientError
import pytest

from quadkit.storage.backends import _s3_upload_mixin
from quadkit.storage.backends import s3 as s3_module
from quadkit.storage.backends.local import LocalDriver
from quadkit.storage.backends.memory import MemoryDriver
from quadkit.storage.backends.registry import DriverRegistry
from quadkit.storage.backends.s3 import S3Driver
from quadkit.storage.config import EncryptionConfig
from quadkit.storage.exceptions import (
    StorageError,
    StorageFileNotFoundError,
    StorageUnsupportedOperationError,
)

# aiobotocore is not installed in this environment, so the driver modules
# nulled out their ``botocore`` reference.  Restore the real (installed)
# botocore so the S3 drivers' ClientError mapping code paths run.
s3_module.botocore = botocore
_s3_upload_mixin.botocore = botocore


def _client_error(code: str, op: str = "GetObject") -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": "simulated"}}, op)


# --------------------------------------------------------------------------
# DriverRegistry selection
# --------------------------------------------------------------------------


class _Cfg:
    """Duck-typed StorageConfig: the factories only touch ``.drivers``."""

    def __init__(self, drivers: dict[str, Any] | None = None) -> None:
        self.drivers = drivers or {}


class _CfgVal:
    def __init__(self, **values: Any) -> None:
        for key, value in values.items():
            setattr(self, key, value)


def test_registry_selects_builtin_drivers() -> None:
    registry = DriverRegistry()
    assert isinstance(registry.get_driver("memory", _Cfg()), MemoryDriver)
    local = registry.get_driver("local", _Cfg())
    assert isinstance(local, LocalDriver)
    # local factory reads driver-specific config
    cfg = _Cfg({"local": _CfgVal(root_dir="/var/storage", base_url="http://x")})
    assert str(registry.get_driver("local", cfg).root_dir) == "/var/storage"

    assert "memory" in registry.available_drivers()
    assert registry.available_drivers() == sorted(registry.available_drivers())

    with pytest.raises(ValueError, match="Unknown storage driver"):
        registry.get_driver("nope", _Cfg())

    # third-party extension point
    registry.register("custom", lambda _config: MemoryDriver())
    assert isinstance(registry.get_driver("custom", _Cfg()), MemoryDriver)


def test_registry_s3_requires_bucket() -> None:
    registry = DriverRegistry()
    with pytest.raises(ValueError, match="bucket"):
        registry.get_driver("s3", _Cfg({"s3": _CfgVal(region="us-east-1")}))


def test_registry_r2_requires_full_credentials() -> None:
    registry = DriverRegistry()
    r2 = _CfgVal(bucket="b", endpoint_url="https://r2.example.com")
    with pytest.raises(ValueError, match="access_key"):
        registry.get_driver("r2", _Cfg({"r2": r2}))


def test_registry_azure_requires_full_credentials() -> None:
    registry = DriverRegistry()
    with pytest.raises(ValueError, match="account_name"):
        registry.get_driver("azure", _Cfg({"azure": _CfgVal()}))
    with pytest.raises(ValueError, match="account_key"):
        registry.get_driver("azure", _Cfg({"azure": _CfgVal(account_name="acc")}))
    with pytest.raises(ValueError, match="container"):
        registry.get_driver(
            "azure",
            _Cfg({"azure": _CfgVal(account_name="acc", account_key="k")}),
        )


# --------------------------------------------------------------------------
# MemoryDriver full protocol
# --------------------------------------------------------------------------


async def test_memory_driver_round_trip() -> None:
    driver = MemoryDriver()
    info = await driver.upload("docs/a.txt", "hello", content_type="text/plain")
    assert info.size == 5
    assert await driver.download("docs/a.txt") == b"hello"
    assert await driver.exists("docs/a.txt") is True
    assert await driver.exists("missing") is False

    info = await driver.info("docs/a.txt")
    assert info.content_type == "text/plain"
    assert info.size == 5

    await driver.upload("docs/b.md", b"world")
    await driver.upload("images/c.png", b"pngdata")
    listed = [f.path async for f in driver.list("docs")]
    assert listed == ["docs/a.txt", "docs/b.md"]

    await driver.delete("docs/b.md")
    assert await driver.exists("docs/b.md") is False
    with pytest.raises(StorageFileNotFoundError):
        await driver.download("missing")
    with pytest.raises(StorageFileNotFoundError):
        await driver.info("missing")

    assert await driver.get_url("docs/a.txt") == "memory://docs/a.txt"
    with pytest.raises(StorageUnsupportedOperationError):
        await driver.get_presigned_url("docs/a.txt")

    health = await driver.health_check()
    assert health.status.value == "healthy"


# --------------------------------------------------------------------------
# LocalDriver round-trip + traversal protection
# --------------------------------------------------------------------------


async def test_local_driver_round_trip_and_traversal(tmp_path: Any) -> None:
    driver = LocalDriver(root_dir=str(tmp_path), base_url="http://files.test")
    await driver.upload("notes/hello.txt", "local content")
    assert await driver.download("notes/hello.txt") == b"local content"

    info = await driver.info("notes/hello.txt")
    assert info.size == len(b"local content")

    await driver.copy("notes/hello.txt", "notes/copy.txt")
    assert await driver.download("notes/copy.txt") == b"local content"
    await driver.move("notes/copy.txt", "notes/moved.txt")
    assert await driver.exists("notes/copy.txt") is False
    assert await driver.download("notes/moved.txt") == b"local content"

    url = await driver.get_url("notes/hello.txt")
    assert url.startswith("http://files.test/")

    # directory traversal is rejected
    with pytest.raises(StorageError):
        await driver.upload("../escape.txt", "nope")
    with pytest.raises(StorageError):
        await driver.download("../../etc/passwd")

    health = await driver.health_check()
    assert health.status.value == "healthy"


# --------------------------------------------------------------------------
# S3Driver with an injected fake client
# --------------------------------------------------------------------------


class _FakeBody:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self) -> bytes:
        return self._data


class _FakeS3Client:
    def __init__(self) -> None:
        self.objects: dict[str, dict[str, Any]] = {}
        self.put_calls: list[dict[str, Any]] = []

    async def put_object(self, **params: Any) -> dict[str, Any]:
        self.put_calls.append(params)
        self.objects[params["Key"]] = params
        return {"ETag": '"fake-etag"'}

    async def get_object(self, Bucket: str, Key: str) -> dict[str, Any]:
        if Key not in self.objects:
            raise _client_error("NoSuchKey")
        return {"Body": _FakeBody(self.objects[Key]["Body"])}

    async def head_object(self, Bucket: str, Key: str) -> dict[str, Any]:
        if Key not in self.objects:
            raise _client_error("NotFound", "HeadObject")
        return {
            "ContentLength": len(self.objects[Key]["Body"]),
            "ContentType": self.objects[Key].get(
                "ContentType", "application/octet-stream"
            ),
            "ETag": '"fake-etag"',
        }

    async def delete_object(self, Bucket: str, Key: str) -> dict[str, Any]:
        self.objects.pop(Key, None)
        return {}

    async def generate_presigned_url(
        self, method: str, Params: dict[str, Any], ExpiresIn: int
    ) -> str:
        return f"https://s3.fake/{Params['Key']}?op={method}&expires={ExpiresIn}"

    async def head_bucket(self, Bucket: str) -> dict[str, Any]:
        return {}


def _make_s3_driver(fake: _FakeS3Client, **overrides: Any) -> S3Driver:
    """Construct S3Driver without aiobotocore by injecting a fake client."""
    driver = S3Driver.__new__(S3Driver)
    driver.bucket = "test-bucket"
    driver.region = "us-east-1"
    driver.access_key = None
    driver.secret_key = None
    driver.endpoint_url = None
    driver.public_url = None
    driver.multipart_threshold = 8 * 1024 * 1024
    driver.multipart_chunk_size = 8 * 1024 * 1024
    driver.encryption = EncryptionConfig()
    driver._session = None  # noqa: SLF001 — never used with an injected client
    driver._client_ctx = None  # noqa: SLF001
    driver._s3_client = fake  # noqa: SLF001
    for key, value in overrides.items():
        setattr(driver, key, value)
    return driver


async def test_s3_upload_download_round_trip_and_mapping() -> None:
    fake = _FakeS3Client()
    driver = _make_s3_driver(fake)

    # leading slashes are normalized away from the key
    info = await driver.upload(
        "/docs/readme.txt", "readme bytes", content_type="text/plain"
    )
    assert info.path == "docs/readme.txt"
    assert fake.put_calls[0]["Bucket"] == "test-bucket"
    assert fake.put_calls[0]["Key"] == "docs/readme.txt"
    assert fake.put_calls[0]["Body"] == b"readme bytes"
    assert fake.put_calls[0]["ContentType"] == "text/plain"
    assert info.etag == '"fake-etag"'

    assert await driver.download("docs/readme.txt") == b"readme bytes"
    assert await driver.exists("docs/readme.txt") is True
    info = await driver.info("docs/readme.txt")
    assert info.size == len(b"readme bytes")
    assert info.content_type == "text/plain"

    await driver.delete("docs/readme.txt")
    assert await driver.exists("docs/readme.txt") is False


async def test_s3_error_mapping() -> None:
    fake = _FakeS3Client()
    driver = _make_s3_driver(fake)

    with pytest.raises(StorageFileNotFoundError):
        await driver.download("missing.txt")
    with pytest.raises(StorageFileNotFoundError):
        await driver.info("missing.txt")
    assert await driver.exists("missing.txt") is False

    # non-NotFound errors map to the generic StorageError
    def explode(**kwargs: Any) -> Any:
        raise _client_error("AccessDenied", "HeadObject")

    fake.head_object = explode  # type: ignore[method-assign]
    with pytest.raises(StorageError, match="exists check failed"):
        await driver.exists("forbidden.txt")


async def test_s3_upload_error_and_path_sanitization() -> None:
    fake = _FakeS3Client()
    driver = _make_s3_driver(fake)

    def deny(**kwargs: Any) -> Any:
        raise _client_error("AccessDenied", "PutObject")

    fake.put_object = deny  # type: ignore[method-assign]
    with pytest.raises(StorageError, match="upload failed"):
        await driver.upload("secret.txt", "data")

    # traversal components are stripped from keys
    good = _FakeS3Client()
    safe = _make_s3_driver(good)
    await safe.upload("../../etc/passwd", "x")
    assert good.objects
    sanitized_keys = [key.split("/") for key in good.objects]
    for parts in sanitized_keys:
        assert ".." not in parts


async def test_s3_presigned_and_public_urls() -> None:
    fake = _FakeS3Client()
    driver = _make_s3_driver(fake)
    url = await driver.get_presigned_url("a/b.txt", expires_in=timedelta(minutes=5))
    assert url == "https://s3.fake/a/b.txt?op=get_object&expires=300"
    put_url = await driver.get_presigned_url("a/b.txt", method="PUT")
    assert "op=put_object" in put_url

    # default AWS-style URL
    assert (
        await driver.get_url("a/b.txt")
        == "https://test-bucket.s3.us-east-1.amazonaws.com/a/b.txt"
    )
    # endpoint-based URL (MinIO / R2 API)
    endpoint_driver = _make_s3_driver(
        _FakeS3Client(), endpoint_url="https://minio.internal:9000"
    )
    assert (
        await endpoint_driver.get_url("a/b.txt")
        == "https://minio.internal:9000/test-bucket/a/b.txt"
    )
    # custom public domain wins
    public_driver = _make_s3_driver(
        _FakeS3Client(), public_url="https://cdn.example.com/"
    )
    assert await public_driver.get_url("a/b.txt") == "https://cdn.example.com/a/b.txt"

    health = await driver.health_check()
    assert health.status.value == "healthy"
