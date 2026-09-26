"""Unit tests for storage exceptions."""

from __future__ import annotations

import pytest
from quadkit.contracts.exceptions import DomainError, QuadkitError

from quadkit.storage import exceptions as storage_exc


class TestStorageError:
    def test_inheritance(self) -> None:
        assert issubclass(storage_exc.StorageError, QuadkitError)
        assert hasattr(storage_exc.StorageError, "_code")

    def test_code(self) -> None:
        exc = storage_exc.StorageError("test message")
        assert exc._code == "QK_ERR_STORE_001"


class TestStorageFileNotFoundError:
    def test_inheritance(self) -> None:
        assert issubclass(storage_exc.StorageFileNotFoundError, DomainError)

    def test_code(self) -> None:
        exc = storage_exc.StorageFileNotFoundError("test message")
        assert exc._code == "QK_ERR_STORE_002"


class TestStorageUnsupportedOperationError:
    def test_inheritance(self) -> None:
        assert issubclass(storage_exc.StorageUnsupportedOperationError, storage_exc.StorageError)

    def test_code(self) -> None:
        exc = storage_exc.StorageUnsupportedOperationError("test message")
        assert exc._code == "QK_ERR_STORE_003"


class TestTransactionError:
    def test_inheritance(self) -> None:
        assert issubclass(storage_exc.TransactionError, storage_exc.StorageError)

    def test_code(self) -> None:
        exc = storage_exc.TransactionError("test message")
        assert exc._code == "QK_ERR_STORE_004"


class TestQuotaExceededError:
    def test_inheritance(self) -> None:
        assert issubclass(storage_exc.QuotaExceededError, storage_exc.StorageError)

    def test_code(self) -> None:
        exc = storage_exc.QuotaExceededError("test message")
        assert exc._code == "QK_ERR_STORE_005"


class TestInvalidPathError:
    def test_inheritance(self) -> None:
        assert issubclass(storage_exc.InvalidPathError, storage_exc.StorageError)

    def test_code(self) -> None:
        exc = storage_exc.InvalidPathError("test message")
        assert exc._code == "QK_ERR_STORE_006"


class TestStorageUnavailableError:
    def test_inheritance(self) -> None:
        assert issubclass(storage_exc.StorageUnavailableError, storage_exc.StorageError)

    def test_code(self) -> None:
        exc = storage_exc.StorageUnavailableError("test message")
        assert exc._code == "QK_ERR_STORE_007"


class TestChecksumMismatchError:
    def test_inheritance(self) -> None:
        assert issubclass(storage_exc.ChecksumMismatchError, storage_exc.StorageError)

    def test_code(self) -> None:
        exc = storage_exc.ChecksumMismatchError("test message")
        assert exc._code == "QK_ERR_STORE_008"


class TestExceptionMessage:
    def test_message_preserved(self) -> None:
        exc = storage_exc.StorageFileNotFoundError("file not found: myfile.txt")
        assert "myfile.txt" in str(exc)


class TestExceptionChaining:
    def test_chaining(self) -> None:
        original = ValueError("original error")
        exc = storage_exc.StorageError("wrapper error")
        exc.__cause__ = original
        assert exc.__cause__ is original