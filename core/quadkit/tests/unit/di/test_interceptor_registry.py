"""Tests for InterceptorRegistry — priority ordering and concurrency safety.

Covers FAANG findings:
  M-01: interceptor priority was silently ignored (insertion-order only)
  M-02: concurrent add_global / add_for_type calls could corrupt list state
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock

from quadkit.di.extensions.interceptors import InterceptorRegistry


class TestInterceptorRegistryPriority:
    def test_global_interceptors_returned_in_priority_order(self) -> None:
        """Interceptors registered with a lower priority int run first."""
        registry = InterceptorRegistry()
        low = MagicMock()
        high = MagicMock()
        registry.add_global(low, priority=10)
        registry.add_global(high, priority=1)

        result = registry.get_interceptors(object)

        assert result[0] is high
        assert result[1] is low

    def test_type_interceptors_returned_in_priority_order(self) -> None:
        """Type-specific interceptors respect priority regardless of insertion order."""
        registry = InterceptorRegistry()
        first = MagicMock()
        second = MagicMock()
        registry.add_for_type(str, second, priority=20)
        registry.add_for_type(str, first, priority=5)

        result = registry.get_interceptors(str)

        assert result[0] is first
        assert result[1] is second

    def test_global_precedes_type_specific(self) -> None:
        """Global interceptors always appear before type-specific ones in the result."""
        registry = InterceptorRegistry()
        glbl = MagicMock()
        specific = MagicMock()
        registry.add_global(glbl, priority=0)
        registry.add_for_type(str, specific, priority=0)

        result = registry.get_interceptors(str)

        assert result[0] is glbl
        assert result[1] is specific

    def test_default_priority_zero_preserves_insertion_order_for_equal_priorities(
        self,
    ) -> None:
        """Equal-priority interceptors stay in insertion order (sort is stable)."""
        registry = InterceptorRegistry()
        a = MagicMock()
        b = MagicMock()
        c = MagicMock()
        registry.add_global(a, priority=0)
        registry.add_global(b, priority=0)
        registry.add_global(c, priority=0)

        result = registry.get_interceptors(object)

        assert result == [a, b, c]

    def test_no_interceptors_returns_empty_list(self) -> None:
        registry = InterceptorRegistry()
        assert registry.get_interceptors(str) == []

    def test_global_only_no_type_specific(self) -> None:
        """get_interceptors returns globals even when no type-specific ones exist."""
        registry = InterceptorRegistry()
        mock = MagicMock()
        registry.add_global(mock, priority=0)

        result = registry.get_interceptors(int)  # unregistered type

        assert result == [mock]

    def test_type_specific_not_returned_for_other_types(self) -> None:
        """Type-specific interceptors are not leaked to unrelated types."""
        registry = InterceptorRegistry()
        mock = MagicMock()
        registry.add_for_type(str, mock, priority=0)

        result = registry.get_interceptors(int)

        assert result == []


class TestInterceptorRegistryConcurrency:
    def test_concurrent_add_global_does_not_corrupt_state(self) -> None:
        """Concurrent add_global calls from multiple threads must not raise or lose entries."""
        registry = InterceptorRegistry()
        errors: list[Exception] = []

        def register_many() -> None:
            try:
                for i in range(50):
                    registry.add_global(MagicMock(), priority=i)
            except Exception as e:  # noqa: BLE001
                errors.append(e)

        threads = [threading.Thread(target=register_many) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(registry.get_interceptors(object)) == 200  # 4 threads x 50

    def test_concurrent_add_for_type_does_not_corrupt_state(self) -> None:
        """Concurrent add_for_type calls from multiple threads must not raise or lose entries."""
        registry = InterceptorRegistry()
        errors: list[Exception] = []

        def register_many() -> None:
            try:
                for i in range(50):
                    registry.add_for_type(str, MagicMock(), priority=i)
            except Exception as e:  # noqa: BLE001
                errors.append(e)

        threads = [threading.Thread(target=register_many) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        # 4 threads x 50 type-specific (no globals)
        assert len(registry.get_interceptors(str)) == 200

    def test_read_during_write_does_not_raise(self) -> None:
        """get_interceptors must never raise even when called during concurrent writes."""
        registry = InterceptorRegistry()
        errors: list[Exception] = []

        def write_loop() -> None:
            try:
                for i in range(100):
                    registry.add_global(MagicMock(), priority=i)
            except Exception as e:  # noqa: BLE001
                errors.append(e)

        def read_loop() -> None:
            try:
                for _ in range(200):
                    registry.get_interceptors(object)
            except Exception as e:  # noqa: BLE001
                errors.append(e)

        threads = [
            threading.Thread(target=write_loop),
            threading.Thread(target=read_loop),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
