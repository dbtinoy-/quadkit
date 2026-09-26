"""Tests for StorageModule pattern."""

from __future__ import annotations

import pytest

from quadkit.contracts import BlobStoreProtocol
from quadkit.di.module import DynamicModule
from quadkit.storage.module import StorageModule


def test_storage_module_has_configure() -> None:
    """StorageModule must have configure() classmethod."""
    assert hasattr(StorageModule, 'configure')
    assert callable(StorageModule.configure)


def test_storage_module_configure_returns_dynamic_module() -> None:
    """StorageModule.configure() must return DynamicModule."""
    result = StorageModule.configure()
    assert isinstance(result, DynamicModule)


def test_storage_module_exports_blob_store_protocol() -> None:
    """StorageModule must export BlobStoreProtocol."""
    module = StorageModule.configure()
    assert BlobStoreProtocol in module.exports
