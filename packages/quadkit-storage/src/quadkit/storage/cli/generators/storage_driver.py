"""Storage driver generator for creating custom storage backends."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quadkit.codegen import GenerationResult, GeneratorBase, parse_fields
from quadkit.contracts.cli.generators import resolve_options


class StorageDriverGenerator(GeneratorBase):
    """Generate a storage driver aligned with :class:`AbstractDriver`.

    The emitted module implements the complete storage contract
    (``upload`` / ``download`` / ``stream`` / ``delete`` / ``exists`` /
    ``info`` / ``list`` / ``get_url`` / ``get_presigned_url`` /
    ``health_check``) with the same in-memory shape as
    :class:`~quadkit.storage.backends.memory.MemoryDriver`, so the
    scaffold is runnable before backend-specific logic is added.
    """

    name = "storage_driver"
    description = "Generate a file storage backend driver"
    default_output_dir = "src/storage/backends"

    def __init__(self, output_dir: str | Path = "src/storage/backends") -> None:
        super().__init__(output_dir=output_dir)

    def generate(
        self,
        name: str,
        *,
        fields_str: str | None = None,
        dry_run: bool = False,
        force: bool = False,
        **options: Any,
    ) -> GenerationResult:
        """Generate a storage driver module.

        Args:
            name: Driver name, e.g. ``"WidgetStorage"`` or ``"widget_storage"``.
            fields_str: Optional ``name:type`` field list in parser syntax.
            dry_run: Compute output paths without writing.
            force: Overwrite an existing file.

        Returns:
            ``GenerationResult`` with created/skipped/overwritten paths.
        """
        driver_name = self._to_pascal_case(name)
        driver_snake = self._to_snake_case(name)
        driver_type = str(options.get("driver_type", "custom"))

        context: dict[str, Any] = {
            "driver_name": driver_name,
            "driver_name_snake": driver_snake,
            "driver_type": driver_type,
            "fields": parse_fields(fields_str or ""),
        }
        content = self.render_template("storage_driver.py.jinja2", context)
        file_path = self.output_dir / f"{driver_snake}.py"
        self.stage(file_path, content)
        return self.finalize(self.commit(resolve_options(dry_run=dry_run, force=force)))


__all__ = ["StorageDriverGenerator"]
