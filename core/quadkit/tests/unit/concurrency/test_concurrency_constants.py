"""Tests for concurrency constants module."""

from __future__ import annotations

from quadkit.concurrency.constants import (
    DEFAULT_CHANNEL_CAPACITY,
    DEFAULT_DISPATCHER_SHUTDOWN_TIMEOUT,
    DEFAULT_SEMAPHORE_TIMEOUT,
    DEFAULT_WORKER_THREADS,
    ENV_NESTED_DELIMITER,
    ENV_PREFIX,
)


class TestConcurrencyConstants:
    """Tests for concurrency constants."""

    def test_env_prefix(self) -> None:
        assert ENV_PREFIX == "QK_CONCURRENCY__"

    def test_env_nested_delimiter(self) -> None:
        assert ENV_NESTED_DELIMITER == "__"

    def test_default_channel_capacity(self) -> None:
        assert DEFAULT_CHANNEL_CAPACITY == 100
        assert isinstance(DEFAULT_CHANNEL_CAPACITY, int)

    def test_default_semaphore_timeout(self) -> None:
        assert DEFAULT_SEMAPHORE_TIMEOUT == 30.0
        assert isinstance(DEFAULT_SEMAPHORE_TIMEOUT, float)

    def test_default_worker_threads(self) -> None:
        assert DEFAULT_WORKER_THREADS == 4
        assert isinstance(DEFAULT_WORKER_THREADS, int)

    def test_default_dispatcher_shutdown_timeout(self) -> None:
        assert DEFAULT_DISPATCHER_SHUTDOWN_TIMEOUT == 10.0
        assert isinstance(DEFAULT_DISPATCHER_SHUTDOWN_TIMEOUT, float)
