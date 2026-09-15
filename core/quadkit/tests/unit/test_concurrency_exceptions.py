"""Unit tests for concurrency exceptions."""

import pytest

from quadkit.concurrency.exceptions import (
    AsyncError,
    CancellationScopeError,
    ChannelClosedError,
    ChannelFullError,
    ConcurrencyError,
    DispatcherError,
    StructuredParallelismError,
    TaskGroupError,
)


class TestConcurrencyError:
    def test_inheritance(self) -> None:
        assert issubclass(ConcurrencyError, Exception)

    def test_code(self) -> None:
        assert ConcurrencyError._code == "QK_ERR_CONC_001"

    def test_default_message(self) -> None:
        exc = ConcurrencyError()
        assert "Concurrency error" in str(exc)


class TestAsyncError:
    def test_inheritance(self) -> None:
        assert issubclass(AsyncError, ConcurrencyError)

    def test_code(self) -> None:
        assert AsyncError._code == "QK_ERR_CONC_002"

    def test_custom_message(self) -> None:
        exc = AsyncError(message="Custom async error")
        assert "Custom async error" in str(exc)


class TestChannelClosedError:
    def test_inheritance(self) -> None:
        assert issubclass(ChannelClosedError, ConcurrencyError)

    def test_code(self) -> None:
        assert ChannelClosedError._code == "QK_ERR_CONC_003"

    def test_default_message(self) -> None:
        exc = ChannelClosedError()
        assert "Channel is closed" in str(exc)


class TestChannelFullError:
    def test_inheritance(self) -> None:
        assert issubclass(ChannelFullError, ConcurrencyError)

    def test_code(self) -> None:
        assert ChannelFullError._code == "QK_ERR_CONC_004"

    def test_capacity_attribute(self) -> None:
        exc = ChannelFullError(capacity=10)
        assert exc.capacity == 10

    def test_capacity_in_details(self) -> None:
        exc = ChannelFullError(capacity=5)
        assert exc.details.get("capacity") == 5


class TestDispatcherError:
    def test_inheritance(self) -> None:
        assert issubclass(DispatcherError, ConcurrencyError)

    def test_code(self) -> None:
        assert DispatcherError._code == "QK_ERR_CONC_005"


class TestStructuredParallelismError:
    def test_inheritance(self) -> None:
        assert issubclass(StructuredParallelismError, ConcurrencyError)

    def test_code(self) -> None:
        assert StructuredParallelismError._code == "QK_ERR_CONC_006"


class TestTaskGroupError:
    def test_inheritance(self) -> None:
        assert issubclass(TaskGroupError, StructuredParallelismError)

    def test_code(self) -> None:
        assert TaskGroupError._code == "QK_ERR_CONC_007"


class TestCancellationScopeError:
    def test_inheritance(self) -> None:
        assert issubclass(CancellationScopeError, StructuredParallelismError)

    def test_code(self) -> None:
        assert CancellationScopeError._code == "QK_ERR_CONC_008"