"""Tests for concurrency exceptions."""

import pytest
from quadkit.concurrency.exceptions import (
    ConcurrencyError,
    AsyncError,
    ChannelClosedError,
    ChannelFullError,
    StructuredParallelismError,
    TaskGroupError,
    CancellationScopeError,
)


class TestConcurrencyError:
    def test_code(self) -> None:
        exc = ConcurrencyError()
        assert exc.code == "QK_ERR_CONC_001"


class TestAsyncError:
    def test_code(self) -> None:
        exc = AsyncError()
        assert exc.code == "QK_ERR_CONC_002"


class TestChannelClosedError:
    def test_code(self) -> None:
        exc = ChannelClosedError()
        assert exc.code == "QK_ERR_CONC_003"

    def test_default_message(self) -> None:
        exc = ChannelClosedError()
        assert exc.message == "Channel is closed"


class TestChannelFullError:
    def test_code(self) -> None:
        exc = ChannelFullError()
        assert exc.code == "QK_ERR_CONC_004"

    def test_with_capacity(self) -> None:
        exc = ChannelFullError(capacity=10)
        assert exc.capacity == 10
        assert exc.details.get("capacity") == 10


class TestStructuredParallelismError:
    def test_code(self) -> None:
        exc = StructuredParallelismError()
        assert exc.code == "QK_ERR_CONC_006"


class TestTaskGroupError:
    def test_code(self) -> None:
        exc = TaskGroupError()
        assert exc.code == "QK_ERR_CONC_007"


class TestCancellationScopeError:
    def test_code(self) -> None:
        exc = CancellationScopeError()
        assert exc.code == "QK_ERR_CONC_008"
