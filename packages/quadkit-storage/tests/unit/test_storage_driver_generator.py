"""Unit tests for the storage driver generator."""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import py_compile
from types import ModuleType

from quadkit.storage.cli.generators.storage_driver import StorageDriverGenerator


class TestStorageDriverGenerator:
    def test_generates_driver_file(self, tmp_path: Path) -> None:
        gen = StorageDriverGenerator(output_dir=str(tmp_path))
        result = gen.generate("WidgetStorage")
        generated_file = tmp_path / "widget_storage.py"
        assert result.files_created == [generated_file]
        assert generated_file.exists()

    def test_generated_file_is_valid_python(self, tmp_path: Path) -> None:
        gen = StorageDriverGenerator(output_dir=str(tmp_path))
        gen.generate("WidgetStorage")
        py_compile.compile(tmp_path / "widget_storage.py", doraise=True)

    def test_generated_content_imports_storage_surface(self, tmp_path: Path) -> None:
        gen = StorageDriverGenerator(output_dir=str(tmp_path))
        gen.generate("WidgetStorage")
        content = (tmp_path / "widget_storage.py").read_text()
        assert (
            "from quadkit.storage.backends import AbstractDriver as BaseDriver"
            in content
        )
        assert "utcnow" not in content

    def test_dry_run_creates_no_files_on_disk(self, tmp_path: Path) -> None:
        gen = StorageDriverGenerator(output_dir=str(tmp_path))
        result = gen.generate("WidgetStorage", dry_run=True)
        assert result.files_created == [tmp_path / "widget_storage.py"]
        assert not (tmp_path / "widget_storage.py").exists()

    def test_files_skipped_on_existing_without_force(self, tmp_path: Path) -> None:
        gen = StorageDriverGenerator(output_dir=str(tmp_path))
        gen.generate("WidgetStorage")
        result = gen.generate("WidgetStorage")
        assert result.files_skipped == [tmp_path / "widget_storage.py"]
        assert result.files_created == []

    def test_force_overwrites_existing_file(self, tmp_path: Path) -> None:
        gen = StorageDriverGenerator(output_dir=str(tmp_path))
        gen.generate("WidgetStorage")
        result = gen.generate("WidgetStorage", force=True)
        assert result.files_overwritten == [tmp_path / "widget_storage.py"]

    async def test_generated_driver_roundtrip(self, tmp_path: Path) -> None:
        """The scaffold implements the AbstractDriver contract end to end."""
        gen = StorageDriverGenerator(output_dir=str(tmp_path))
        gen.generate("WidgetStorage")

        spec = spec_from_file_location(
            "widget_storage_generated", tmp_path / "widget_storage.py"
        )
        assert spec is not None
        assert spec.loader is not None
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        assert isinstance(module, ModuleType)

        driver = module.WidgetStorageDriver()
        info = await driver.upload("demo/hello.txt", b"hello world")
        assert info.path == "demo/hello.txt"
        assert await driver.download("demo/hello.txt") == b"hello world"
        assert await driver.exists("demo/hello.txt")
        listed = [item.path async for item in driver.list(prefix="demo/")]
        assert listed == ["demo/hello.txt"]
        await driver.delete("demo/hello.txt")
        assert not await driver.exists("demo/hello.txt")
