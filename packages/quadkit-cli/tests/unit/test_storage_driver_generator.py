"""Regression tests for the storage driver generator."""

from __future__ import annotations

from pathlib import Path
import py_compile

from quadkit.cli.registry.generator import GeneratorAdapter
from quadkit.storage.cli.generators.storage_driver import StorageDriverGenerator


class TestStorageDriverGenerator:
    """Verify storage driver generation stays aligned with storage backends."""

    def test_adapter_uses_backend_output_dir(self) -> None:
        adapter = GeneratorAdapter(StorageDriverGenerator, "src/storage/backends")
        assert adapter.get_default_output_dir() == "src/storage/backends"

    def test_generate_uses_backend_import_surface(self, tmp_path: Path) -> None:
        generator = StorageDriverGenerator(output_dir=str(tmp_path))
        result = generator.generate("WidgetStorage", force=True)
        generated_file = tmp_path / "widget_storage.py"

        assert result.files_created == [generated_file]
        assert result.files_overwritten == []
        assert generated_file.exists()
        py_compile.compile(generated_file, doraise=True)

        content = generated_file.read_text()
        assert (
            "from quadkit.storage.backends import AbstractDriver as BaseDriver"
            in content
        )

    def test_dry_run_reports_path_without_writing(self, tmp_path: Path) -> None:
        generator = StorageDriverGenerator(output_dir=str(tmp_path))
        result = generator.generate("WidgetStorage", dry_run=True)
        assert result.files_created == [tmp_path / "widget_storage.py"]
        assert not (tmp_path / "widget_storage.py").exists()

    def test_existing_file_is_skipped_without_force(self, tmp_path: Path) -> None:
        generator = StorageDriverGenerator(output_dir=str(tmp_path))
        generator.generate("WidgetStorage")
        result = generator.generate("WidgetStorage")
        assert result.files_skipped == [tmp_path / "widget_storage.py"]
        assert result.files_created == []
