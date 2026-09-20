"""Contract compliance suite for ``RotatableSecretStoreProtocol`` implementations.

Subclass :class:`StoreConformanceSuite` and provide a ``make_store`` fixture
to verify any rotatable secret store satisfies the contract::

    from quadkit.testing.compliance import StoreConformanceSuite
    from quadkit.testing.fakes import FakeRotatableSecretStore

    class TestMyStore(StoreConformanceSuite):
        @pytest.fixture
        def make_store(self):
            return FakeRotatableSecretStore
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from quadkit.testing.fakes.secrets import FakeRotatableSecretStore

    RotatableStoreFactory = Callable[[], "FakeRotatableSecretStore"]
else:
    RotatableStoreFactory = Any

import pytest

__all__ = ["StoreConformanceSuite", "parametrize_rotatable_store"]


def parametrize_rotatable_store(
    stores: list[tuple[str, Callable[[], Any]]],
) -> Any:
    """Parametrize a test class over ``RotatableSecretStoreProtocol`` backends.

    Usage in a test module::

        from quadkit.testing.compliance import (
            parametrize_rotatable_store,
            StoreConformanceSuite,
        )
        from my_store import MyStore

        @parametrize_rotatable_store([
            ("fake", lambda: FakeRotatableSecretStore()),
            ("my", lambda: MyStore()),
        ])
        class TestMyConformance(StoreConformanceSuite):
            ...
    """
    return pytest.mark.parametrize(
        "make_store",
        [pytest.param(fn, id=name) for name, fn in stores],
    )


class StoreConformanceSuite:
    """Mixin with parameterized conformance tests for
    ``RotatableSecretStoreProtocol`` backends.

    Subclasses must provide a fixture ``make_store`` returning a
    ``RotatableStoreFactory`` (a zero-argument callable returning a fresh
    store instance).
    """

    async def test_get_missing_returns_none(
        self, make_store: RotatableStoreFactory
    ) -> None:
        store = make_store()
        result = await store.get("nonexistent")
        assert result is None

    async def test_set_and_get(self, make_store: RotatableStoreFactory) -> None:
        store = make_store()
        await store.set("key1", "value1")
        result = await store.get("key1")
        assert result == "value1"

    async def test_overwrite(self, make_store: RotatableStoreFactory) -> None:
        store = make_store()
        await store.set("key", "old")
        await store.set("key", "new")
        result = await store.get("key")
        assert result == "new"

    async def test_delete_removes(self, make_store: RotatableStoreFactory) -> None:
        store = make_store()
        await store.set("key", "val")
        await store.delete("key")
        result = await store.get("key")
        assert result is None

    async def test_delete_nonexistent_is_noop(
        self, make_store: RotatableStoreFactory
    ) -> None:
        store = make_store()
        await store.delete("nobody")

    async def test_get_bulk(self, make_store: RotatableStoreFactory) -> None:
        store = make_store()
        await store.set("a", "1")
        await store.set("b", "2")
        result = await store.get_bulk("a", "b", "c")
        assert result == {"a": "1", "b": "2"}

    async def test_rotate_creates_new_version(
        self, make_store: RotatableStoreFactory
    ) -> None:
        store = make_store()
        await store.set("key", "original")
        rotated = await store.rotate("key")
        assert rotated.key == "key"
        assert rotated.value != "original"
        assert rotated.version >= 1

    async def test_rotate_increments_version(
        self, make_store: RotatableStoreFactory
    ) -> None:
        store = make_store()
        await store.set("key", "v0")
        v1 = await store.rotate("key")
        v2 = await store.rotate("key")
        assert v2.version == v1.version + 1

    async def test_rotate_updates_current_value(
        self, make_store: RotatableStoreFactory
    ) -> None:
        store = make_store()
        await store.set("key", "original")
        rotated = await store.rotate("key")
        current = await store.get("key")
        assert current == str(rotated.value)

    async def test_get_version_returns_specific(
        self, make_store: RotatableStoreFactory
    ) -> None:
        store = make_store()
        await store.set("key", "version_1")
        await store.rotate("key")
        v1 = await store.get_version("key", 1)
        assert v1 == "version_1"

    async def test_get_version_missing_is_none(
        self, make_store: RotatableStoreFactory
    ) -> None:
        store = make_store()
        result = await store.get_version("key", 99)
        assert result is None

    async def test_list_versions_order(self, make_store: RotatableStoreFactory) -> None:
        store = make_store()
        await store.set("key", "a")
        await store.rotate("key")
        await store.rotate("key")
        versions = await store.list_versions("key")
        assert len(versions) >= 2
        assert versions[0].version > versions[1].version

    async def test_list_versions_empty(self, make_store: RotatableStoreFactory) -> None:
        store = make_store()
        versions = await store.list_versions("nonexistent")
        assert versions == []

    async def test_get_current_version(self, make_store: RotatableStoreFactory) -> None:
        store = make_store()
        await store.set("key", "latest_value")
        current = await store.get_current_version("key")
        assert current.key == "key"
        assert str(current.value) == "latest_value"

    async def test_get_current_version_missing_raises(
        self, make_store: RotatableStoreFactory
    ) -> None:
        store = make_store()
        try:
            await store.get_current_version("nonexistent")
            pytest.fail("Expected KeyError")
        except KeyError:
            pass
