"""Tests for MappingRegistry thread-safety guarantees."""

from __future__ import annotations

from dataclasses import dataclass
import threading

import pytest

from quadkit.mapping.core.mapper import MappingRegistry


@dataclass
class _Src:
    value: int


@dataclass
class _Dst:
    value: int


class TestMappingRegistryBasic:
    """Basic register / get / unregister contract tests."""

    def test_register_and_get_returns_func(self) -> None:
        registry = MappingRegistry()
        fn = lambda s: _Dst(s.value)  # noqa: E731
        registry.register(_Src, _Dst, fn)
        assert registry.get(_Src, _Dst) is fn

    def test_get_missing_returns_none(self) -> None:
        registry = MappingRegistry()
        assert registry.get(_Src, _Dst) is None

    def test_has_false_before_register(self) -> None:
        registry = MappingRegistry()
        assert registry.has(_Src, _Dst) is False

    def test_has_true_after_register(self) -> None:
        registry = MappingRegistry()
        registry.register(_Src, _Dst, lambda s: _Dst(s.value))
        assert registry.has(_Src, _Dst) is True

    def test_register_duplicate_raises_value_error(self) -> None:
        registry = MappingRegistry()
        fn = lambda s: _Dst(s.value)  # noqa: E731
        registry.register(_Src, _Dst, fn)
        with pytest.raises(ValueError, match="already registered"):
            registry.register(_Src, _Dst, fn)

    def test_unregister_existing_removes_entry(self) -> None:
        registry = MappingRegistry()
        registry.register(_Src, _Dst, lambda s: _Dst(s.value))
        registry.unregister(_Src, _Dst)
        assert registry.has(_Src, _Dst) is False

    def test_unregister_missing_raises_key_error(self) -> None:
        registry = MappingRegistry()
        with pytest.raises(KeyError):
            registry.unregister(_Src, _Dst)


class TestMappingRegistryThreadSafety:
    """Concurrent access must not corrupt the registry."""

    def test_concurrent_register_does_not_corrupt_registry(self) -> None:
        """Many threads each registering distinct type pairs → all present after join."""
        registry = MappingRegistry()
        errors: list[Exception] = []

        # Create N unique (source, dest) type pairs dynamically
        n = 50
        type_pairs: list[tuple[type, type]] = []
        for i in range(n):
            src = type(f"Src{i}", (), {})
            dst = type(f"Dst{i}", (), {})
            type_pairs.append((src, dst))

        def register_one(src: type, dst: type) -> None:
            try:
                registry.register(src, dst, lambda s, _d=dst: _d())
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=register_one, args=(s, d)) for s, d in type_pairs]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Threads raised exceptions: {errors}"
        for src, dst in type_pairs:
            assert registry.has(src, dst), f"Missing mapping {src.__name__} → {dst.__name__}"

    def test_concurrent_get_while_registering_is_safe(self) -> None:
        """Reader threads running while writers register must not raise."""
        registry = MappingRegistry()
        errors: list[Exception] = []

        # Pre-register one pair so readers have something to find
        registry.register(_Src, _Dst, lambda s: _Dst(s.value))

        def reader() -> None:
            for _ in range(100):
                try:
                    registry.get(_Src, _Dst)
                    registry.has(_Src, _Dst)
                except Exception as exc:  # noqa: BLE001
                    errors.append(exc)

        def writer(i: int) -> None:
            src = type(f"WSrc{i}", (), {})
            dst = type(f"WDst{i}", (), {})
            try:
                registry.register(src, dst, lambda s, _d=dst: _d())
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads: list[threading.Thread] = []
        for i in range(20):
            threads.append(threading.Thread(target=writer, args=(i,)))
        for _ in range(5):
            threads.append(threading.Thread(target=reader))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Threads raised exceptions: {errors}"

    def test_concurrent_unregister_does_not_corrupt_registry(self) -> None:
        """Concurrent unregistrations of disjoint keys must all succeed cleanly."""
        registry = MappingRegistry()
        errors: list[Exception] = []

        n = 30
        type_pairs: list[tuple[type, type]] = []
        for i in range(n):
            src = type(f"USrc{i}", (), {})
            dst = type(f"UDst{i}", (), {})
            registry.register(src, dst, lambda s, _d=dst: _d())
            type_pairs.append((src, dst))

        def unregister_one(src: type, dst: type) -> None:
            try:
                registry.unregister(src, dst)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=unregister_one, args=(s, d)) for s, d in type_pairs]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Threads raised exceptions: {errors}"
        for src, dst in type_pairs:
            assert not registry.has(src, dst)
