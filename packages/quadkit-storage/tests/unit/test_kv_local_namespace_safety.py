"""Namespace traversal safety tests for LocalStorage KV backend."""

from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
from uuid import uuid4

import pytest

from quadkit.storage.kv.local import LocalStorage


class TestNamespaceHelper:
    """Tests for the _get_ns_dir helper."""

    @pytest.fixture
    def temp_dir(self) -> Path:
        tmp = Path(tempfile.mkdtemp())
        yield tmp
        shutil.rmtree(tmp, ignore_errors=True)

    @pytest.fixture
    def storage(self, temp_dir: Path) -> LocalStorage:
        return LocalStorage(base_path=temp_dir)

    @pytest.mark.asyncio
    async def test_none_and_empty_map_to_default(self, storage, temp_dir: Path) -> None:
        assert storage._get_ns_dir(None) == (temp_dir / "default").resolve()
        assert storage._get_ns_dir("") == (temp_dir / "default").resolve()

    @pytest.mark.asyncio
    async def test_fully_stripped_maps_to_default(
        self, storage, temp_dir: Path
    ) -> None:
        assert storage._get_ns_dir("!!!???") == (temp_dir / "default").resolve()

    @pytest.mark.asyncio
    async def test_path_metachars_map_to_default(self, storage, temp_dir: Path) -> None:
        assert storage._get_ns_dir("..") == (temp_dir / "default").resolve()
        assert storage._get_ns_dir(".") == (temp_dir / "default").resolve()

    @pytest.mark.asyncio
    async def test_traversal_filters_to_flat_name(
        self, storage, temp_dir: Path
    ) -> None:
        ns_dir = storage._get_ns_dir("../../escape")
        assert ns_dir == (temp_dir / "....escape").resolve()
        assert "/" not in "".join(p for p in ns_dir.parts if p not in temp_dir.parts)

    @pytest.mark.asyncio
    async def test_legit_namespaces_unchanged(self, storage, temp_dir: Path) -> None:
        assert storage._get_ns_dir("tenant-a") == (temp_dir / "tenant-a").resolve()
        assert storage._get_ns_dir("style_2") == (temp_dir / "style_2").resolve()
        assert storage._get_ns_dir("channel.7") == (temp_dir / "channel.7").resolve()

    @pytest.mark.asyncio
    async def test_escaped_target_is_not_relative_to_base(
        self, storage, temp_dir: Path
    ) -> None:
        base = storage.base_path.resolve()
        assert not (base / "..").resolve().is_relative_to(base)


class TestNamespaceContainment:
    """Regression tests for the escape class under base_path containment."""

    @pytest.fixture
    def temp_dir(self) -> Path:
        tmp = Path(tempfile.mkdtemp())
        yield tmp
        shutil.rmtree(tmp, ignore_errors=True)

    @pytest.fixture
    def storage(self, temp_dir: Path) -> LocalStorage:
        return LocalStorage(base_path=temp_dir)

    @pytest.mark.asyncio
    async def test_set_get_stays_inside_base_path(
        self, storage, temp_dir: Path
    ) -> None:
        await storage.connect()
        await storage.set("k", "v", namespace="../../escape")
        path = storage._get_file_path("k", "../../escape")
        assert path.resolve().is_relative_to(storage.base_path.resolve())
        assert await storage.get("k", namespace="../../escape") == "v"

    @pytest.mark.asyncio
    async def test_list_keys_confined_to_base_path(
        self, storage, temp_dir: Path
    ) -> None:
        await storage.connect()
        await storage.set("sentinel", "s", namespace="../../escape")
        keys = await storage.list_keys(namespace="../../escape")
        assert "sentinel" in keys
        for key in keys:
            path = storage._get_file_path(key, "../../escape")
            assert path.resolve().is_relative_to(storage.base_path.resolve())

    @pytest.mark.asyncio
    async def test_clear_never_removes_sibling_directory(
        self, storage, temp_dir: Path
    ) -> None:
        sentinel = temp_dir.parent / f"sentinel_{uuid4()}"
        sentinel.mkdir()
        try:
            result = await storage.clear(namespace=f"../../sentinel_{sentinel.name}")
            assert result is True
            assert sentinel.exists()
        finally:
            shutil.rmtree(sentinel, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_clear_dotdot_confined_to_base_path(
        self, storage, temp_dir: Path
    ) -> None:
        await storage.connect()
        await storage.set("k0", "v0")
        await storage.set("k1", "v1", namespace="alpha")
        await storage.set("k2", "v2", namespace="beta")
        await storage.clear(namespace="..")
        assert temp_dir.exists()
        assert await storage.list_keys() == []
        assert await storage.list_keys(namespace="alpha") == ["k1"]
        assert await storage.list_keys(namespace="beta") == ["k2"]

    @pytest.mark.asyncio
    async def test_default_baselines(self, storage, temp_dir: Path) -> None:
        await storage.connect()
        await storage.set("k", "v")
        assert await storage.get("k", namespace="") == "v"
        assert await storage.get("k", namespace=None) == "v"
        assert await storage.list_keys(namespace="") == ["k"]
        await storage.clear(namespace="")
        assert await storage.list_keys(namespace=None) == []

    @pytest.mark.asyncio
    async def test_legit_namespaces_round_trip_isolated(
        self, storage, temp_dir: Path
    ) -> None:
        await storage.connect()
        await storage.set("k", "a", namespace="tenant-a")
        await storage.set("k", "b", namespace="style_2")
        await storage.set("k", "c", namespace="channel.7")
        assert await storage.get("k", namespace="tenant-a") == "a"
        assert await storage.get("k", namespace="style_2") == "b"
        assert await storage.get("k", namespace="channel.7") == "c"
        assert await storage.list_keys(namespace="tenant-a") == ["k"]

    @pytest.mark.asyncio
    async def test_escape_battery_stays_inside_base_path(
        self, storage, temp_dir: Path
    ) -> None:
        base = storage.base_path.resolve()
        hostile = [
            "..",
            "../..",
            "../../etc",
            "a/b",
            "a\\b",
            "../",
            " ",
            '"',
            "~",
            "\u00e9",
            "%2e%2e",
        ]
        for ns in hostile:
            ns_dir = storage._get_ns_dir(ns)
            assert ns_dir.is_relative_to(base), f"namespace escaped base: {ns!r}"
            assert base in ns_dir.parents
