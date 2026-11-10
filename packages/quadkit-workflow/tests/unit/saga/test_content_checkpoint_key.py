"""Unit tests for ContentCheckpointKey, ContentCheckpointEntry, ContentCheckpointStoreProtocol."""
from __future__ import annotations

import hashlib

import pytest

from quadkit.contracts.workflow.content_checkpoint import (
    ContentCheckpointEntry,
    ContentCheckpointKey,
    ContentCheckpointStoreProtocol,
)


class TestContentCheckpointKey:
    def test_construct(self):
        key = ContentCheckpointKey(
            stage_id="gen-embedding",
            tenant_id="tenant-abc",
            input_hash=b"\x00" * 32,
            config_hash=b"\x01" * 32,
        )
        assert key.stage_id == "gen-embedding"

    def test_as_str_format(self):
        key = ContentCheckpointKey(
            stage_id="gen-embedding",
            tenant_id="tenant-abc",
            input_hash=b"\x00" * 32,
            config_hash=b"\x01" * 32,
        )
        s = key.as_str()
        assert s.startswith("gen-embedding|tenant-abc|")
        assert len(s) > 50

    def test_deterministic(self):
        key1 = ContentCheckpointKey.compute(
            stage_id="gen",
            tenant_id="t1",
            inputs={"text": "hello"},
            stage_handler_version="v1",
            config_affecting_output={"model": "gpt-4"},
        )
        key2 = ContentCheckpointKey.compute(
            stage_id="gen",
            tenant_id="t1",
            inputs={"text": "hello"},
            stage_handler_version="v1",
            config_affecting_output={"model": "gpt-4"},
        )
        assert key1.as_str() == key2.as_str()

    def test_different_inputs_different_keys(self):
        key1 = ContentCheckpointKey.compute(
            stage_id="gen",
            tenant_id="t1",
            inputs={"text": "hello"},
            stage_handler_version="v1",
            config_affecting_output={},
        )
        key2 = ContentCheckpointKey.compute(
            stage_id="gen",
            tenant_id="t1",
            inputs={"text": "world"},
            stage_handler_version="v1",
            config_affecting_output={},
        )
        assert key1.as_str() != key2.as_str()

    def test_different_tenant_different_keys(self):
        key1 = ContentCheckpointKey.compute(
            stage_id="gen",
            tenant_id="t1",
            inputs={"text": "hello"},
            stage_handler_version="v1",
            config_affecting_output={},
        )
        key2 = ContentCheckpointKey.compute(
            stage_id="gen",
            tenant_id="t2",
            inputs={"text": "hello"},
            stage_handler_version="v1",
            config_affecting_output={},
        )
        assert key1.as_str() != key2.as_str()

    def test_different_handler_version_different_keys(self):
        key1 = ContentCheckpointKey.compute(
            stage_id="gen",
            tenant_id="t1",
            inputs={"text": "hello"},
            stage_handler_version="v1",
            config_affecting_output={},
        )
        key2 = ContentCheckpointKey.compute(
            stage_id="gen",
            tenant_id="t1",
            inputs={"text": "hello"},
            stage_handler_version="v2",
            config_affecting_output={},
        )
        assert key1.as_str() != key2.as_str()

    def test_tenant_can_be_none(self):
        key = ContentCheckpointKey.compute(
            stage_id="gen",
            tenant_id=None,
            inputs={"text": "hello"},
            stage_handler_version="v1",
            config_affecting_output={},
        )
        assert "_global" in key.as_str()


class TestContentCheckpointEntry:
    def test_construct(self):
        from datetime import datetime

        entry = ContentCheckpointEntry(
            output={"embedding": [0.1, 0.2]},
            output_blob_ref=None,
            completed_at=datetime(2026, 6, 3),
            stage_handler_version="v1",
            output_size_bytes=42,
            metadata={},
        )
        assert entry.output["embedding"] == [0.1, 0.2]
        assert entry.output_blob_ref is None


class TestContentCheckpointStoreProtocol:
    def test_protocol_methods_exist(self):
        methods = {"get", "set", "evict", "list_by_stage"}
        for m in methods:
            assert hasattr(ContentCheckpointStoreProtocol, m)
