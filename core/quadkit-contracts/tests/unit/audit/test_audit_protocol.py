"""Unit tests for quadkit.contracts.audit protocols."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from quadkit.contracts.audit import (
    AuditEntry,
    AuditEventSeverity,
    AuditLoggerProtocol,
    AuditQuery,
    AuditStoreProtocol,
)


class TestAuditLoggerProtocolRuntime:
    def test_is_runtime_checkable(self) -> None:
        class FakeLogger:
            async def log(self, entry: AuditEntry) -> None: ...
            async def query(self, query: AuditQuery) -> list[AuditEntry]: return []

        assert isinstance(FakeLogger(), AuditLoggerProtocol)

    def test_non_conforming_is_not_logger(self) -> None:
        class NotALogger:
            def write(self) -> None: ...

        assert not isinstance(NotALogger(), AuditLoggerProtocol)


class TestAuditStoreProtocolRuntime:
    def test_is_runtime_checkable(self) -> None:
        class FakeStore:
            async def append(self, entry: AuditEntry) -> None: ...
            async def query(self, query: AuditQuery) -> list[AuditEntry]: return []
            async def count(self, query: AuditQuery) -> int: return 0
            async def delete_expired(self, cutoff: datetime) -> int: return 0

        assert isinstance(FakeStore(), AuditStoreProtocol)

    def test_non_conforming_is_not_store(self) -> None:
        class NotAStore:
            def store(self) -> None: ...

        assert not isinstance(NotAStore(), AuditStoreProtocol)

    def test_has_delete_expired_method(self) -> None:
        assert hasattr(AuditStoreProtocol, "delete_expired")
        assert callable(AuditStoreProtocol.delete_expired)


class TestAuditInitExports:
    def test_all_expected_names_importable(self) -> None:
        from quadkit.contracts.audit import (  # noqa: F401
            AuditEntry,
            AuditEventSeverity,
            AuditLoggerProtocol,
            AuditMismatch,
            AuditQuery,
            AuditStoreProtocol,
            AuditVerifierProtocol,
            RetentionDecision,
            RetentionPolicy,
            RetentionPolicyProtocol,
        )
