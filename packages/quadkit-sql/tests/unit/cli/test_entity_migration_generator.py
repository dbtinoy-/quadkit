"""Column-shape tests for EntityMigrationGenerator.

The migration template hardcodes `id` / `created_at` / `updated_at`, so a
`--fields` list that names one of them is describing the same column, not a
second one. The tests below run the generated `upgrade()` against a recording
stub of alembic's `op`, which is the closest thing to the failure the
generated project hits: `op.create_table` receiving a column name twice.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

PYPROJECT = '[project]\nname = "demo"\nversion = "0.1.0"\n'


def _generate(tmp_path: Path, fields: str | None = None) -> Path:
    """Generate a migration inside an anchored src-layout project.

    Args:
        tmp_path: Scratch project root.
        fields: Optional ``--fields`` specification string.

    Returns:
        Path to the generated revision module.
    """
    from quadkit.sql.cli.generators.entity_migration import EntityMigrationGenerator

    (tmp_path / "pyproject.toml").write_text(PYPROJECT)
    out = tmp_path / "src" / "migrations" / "versions"
    out.mkdir(parents=True, exist_ok=True)
    result = EntityMigrationGenerator(output_dir=out).generate(
        "Order", fields, rev_id="001", table_name="orders"
    )
    return Path(result.files_created[0])


class _RecordingOp:
    """Records what the migration asks alembic to create."""

    def __init__(self) -> None:
        self.tables: dict[str, list[str]] = {}

    def create_table(self, name: str, *columns: object, **_kwargs: object) -> None:
        self.tables[name] = [str(getattr(column, "name", column)) for column in columns]

    def drop_table(self, name: str) -> None:  # pragma: no cover - downgrade only
        self.tables.pop(name, None)


def _run_upgrade(path: Path) -> _RecordingOp:
    """Import the generated revision and run its ``upgrade()``."""
    spec = importlib.util.spec_from_file_location(
        "generated_migration_under_test", path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
        recorder = _RecordingOp()
        module.op = recorder
        module.upgrade()
        return recorder
    finally:
        sys.modules.pop(spec.name, None)


def test_reserved_fields_are_not_rendered_as_extra_columns(tmp_path: Path) -> None:
    """A declared ``id``/``created_at`` is the template's own column."""
    path = _generate(tmp_path, "id:str,created_at:datetime,title:str")

    columns = _run_upgrade(path).tables["orders"]

    assert columns == ["id", "created_at", "updated_at", "title"]


def test_ordinary_fields_are_still_rendered(tmp_path: Path) -> None:
    """Filtering the reserved names must not filter the requested ones."""
    path = _generate(tmp_path, "title:str,count:int,when:datetime")

    columns = _run_upgrade(path).tables["orders"]

    assert columns == ["id", "created_at", "updated_at", "title", "count", "when"]
    source = path.read_text()
    assert 'sa.Column("title", sa.String' in source
    assert 'sa.Column("count", sa.Integer' in source


def test_nullability_follows_the_field_spec(tmp_path: Path) -> None:
    """``name:str?`` is nullable; ``name:str`` is not."""
    path = _generate(tmp_path, "title:str,nickname:str?")

    source = path.read_text()

    assert 'sa.Column("title", sa.String(length=255), nullable=False)' in source
    assert 'sa.Column("nickname", sa.String(length=255), nullable=True)' in source


def test_no_fields_still_creates_the_audit_columns(tmp_path: Path) -> None:
    """Without ``--fields`` the migration is the template's three columns."""
    path = _generate(tmp_path)

    assert _run_upgrade(path).tables["orders"] == ["id", "created_at", "updated_at"]
