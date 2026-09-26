"""Tests for NamedStorageConfig and StorageConfig.backends."""
from __future__ import annotations

import pytest

from quadkit.storage.config import (
    NamedStorageConfig,
    StorageConfig,
    StorageLocalConfig,
    StorageS3Config,
)


class TestNamedStorageConfig:
    def test_requires_name(self) -> None:
        with pytest.raises(Exception):
            NamedStorageConfig()  # type: ignore[call-arg]

    def test_defaults(self) -> None:
        cfg = NamedStorageConfig(name="primary")
        assert cfg.name == "primary"
        assert cfg.driver == "local"
        assert cfg.primary is False
        assert cfg.s3 is None
        assert cfg.local is None

    def test_primary_flag(self) -> None:
        cfg = NamedStorageConfig(name="main", primary=True)
        assert cfg.primary is True

    def test_with_s3_config(self) -> None:
        s3 = StorageS3Config(bucket="my-bucket", region="us-east-1")
        cfg = NamedStorageConfig(name="primary", driver="s3", s3=s3)
        assert cfg.driver == "s3"
        assert cfg.s3.bucket == "my-bucket"

    def test_with_local_config(self) -> None:
        local = StorageLocalConfig(root_dir="/tmp/storage")
        cfg = NamedStorageConfig(name="files", driver="local", local=local)
        assert cfg.local.root_dir == "/tmp/storage"


class TestStorageConfigBackends:
    def test_backends_defaults_to_empty(self) -> None:
        cfg = StorageConfig()
        assert cfg.backends == []

    def test_backends_accepts_named_entries(self) -> None:
        primary = NamedStorageConfig(name="primary", primary=True, driver="memory")
        avatars = NamedStorageConfig(name="avatars", driver="memory")
        cfg = StorageConfig(backends=[primary, avatars])
        assert len(cfg.backends) == 2
        assert cfg.backends[0].name == "primary"
        assert cfg.backends[1].name == "avatars"

    def test_from_named_memory_driver(self) -> None:
        entry = NamedStorageConfig(name="temp", driver="memory")
        result = StorageConfig.from_named(entry)
        assert result.default_driver == "memory"
        assert result.backends == []

    def test_from_named_s3_driver_populates_drivers_dict(self) -> None:
        s3 = StorageS3Config(bucket="my-bucket", region="us-east-1")
        entry = NamedStorageConfig(name="primary", driver="s3", s3=s3)
        result = StorageConfig.from_named(entry)
        assert result.default_driver == "s3"
        assert "s3" in result.drivers
        assert result.drivers["s3"].bucket == "my-bucket"
        assert result.backends == []

    def test_from_named_local_driver_populates_drivers_dict(self) -> None:
        local = StorageLocalConfig(root_dir="/data")
        entry = NamedStorageConfig(name="files", driver="local", local=local)
        result = StorageConfig.from_named(entry)
        assert result.default_driver == "local"
        assert "local" in result.drivers
        assert result.drivers["local"].root_dir == "/data"
