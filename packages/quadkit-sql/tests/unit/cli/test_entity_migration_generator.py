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

import pytest

PYPROJECT = '[project]\nname = "demo"\nversion = "0.1.0"\n'


def _generate(
    tmp_path: Path,
    fields: str | None = None,
    *,
    entity_spec: object | None = None,
) -> Path:
    """Generate a migration inside an anchored src-layout project.

    Args:
        tmp_path: Scratch project root.
        fields: Optional ``--fields`` specification string.
        entity_spec: Optional structured entity contract.

    Returns:
        Path to the generated revision module.
    """
    from quadkit.sql.cli.generators.entity_migration import EntityMigrationGenerator

    (tmp_path / "pyproject.toml").write_text(PYPROJECT)
    out = tmp_path / "src" / "migrations" / "versions"
    out.mkdir(parents=True, exist_ok=True)
    result = EntityMigrationGenerator(output_dir=out).generate(
        "Order",
        fields,
        entity_spec=entity_spec,  # type: ignore[arg-type]
        rev_id="001",
        table_name="orders",
    )
    return Path(result.files_created[0])


class _RecordingOp:
    """Records what the migration asks alembic to create."""

    def __init__(self) -> None:
        self.tables: dict[str, list[str]] = {}
        self.indexes: list[tuple[str, str, tuple[str, ...]]] = []
        self.dropped_indexes: list[str] = []

    def create_table(self, name: str, *columns: object, **_kwargs: object) -> None:
        self.tables[name] = [str(getattr(column, "name", column)) for column in columns]

    def create_index(
        self, name: str, table: str, columns: list[str], **_kwargs: object
    ) -> None:
        self.indexes.append((name, table, tuple(columns)))

    def drop_index(self, name: str, **_kwargs: object) -> None:
        self.dropped_indexes.append(name)

    def drop_table(self, name: str) -> None:
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


def test_fk_syntax_renders_named_foreign_key_and_index(tmp_path: Path) -> None:
    """Table-qualified FK syntax reaches DDL rather than being dropped."""
    from quadkit.contracts.cli.parsers import parse_fields

    field = parse_fields("post_id:uuid!fk=posts.id!ondelete=restrict")[0]
    assert field.fk == "posts.id"
    assert field.on_delete == "restrict"

    path = _generate(tmp_path, "post_id:uuid!fk=posts.id!ondelete=restrict")
    source = path.read_text()

    assert (
        'sa.ForeignKey("posts.id", name="fk_orders_post_id_posts", ondelete="RESTRICT")'
    ) in source
    recorder = _run_upgrade(path)
    assert recorder.tables["orders"] == [
        "id",
        "created_at",
        "updated_at",
        "post_id",
    ]
    assert recorder.indexes == [("ix_orders_post_id", "orders", ("post_id",))]
    assert "op.drop_index('ix_orders_post_id', table_name='orders')" in source
    assert source.index("op.drop_index('ix_orders_post_id'") < source.index(
        'op.drop_table("orders")'
    )


def test_field_string_and_structured_spec_render_identical_fk_ddl(
    tmp_path: Path,
) -> None:
    """The CLI compatibility spelling and EntitySpec are one contract."""
    from quadkit.contracts.cli.parsers import EntitySpec, FieldSpec

    string_root = tmp_path / "string"
    spec_root = tmp_path / "spec"
    string_root.mkdir()
    spec_root.mkdir()
    fields = "post_id:uuid!fk=posts.id!ondelete=cascade,title:str!indexed"
    spec = EntitySpec(
        name="order",
        table_name="orders",
        fields=(
            FieldSpec(
                name="post_id",
                type="uuid",
                fk="posts.id",
                on_delete="cascade",
            ),
            FieldSpec(name="title", type="str", indexed=True),
        ),
    )

    from_string = _generate(string_root, fields).read_text()
    from_spec = _generate(spec_root, entity_spec=spec).read_text()

    assert from_spec == from_string


def test_structured_spec_renders_soft_delete_and_composite_index(
    tmp_path: Path,
) -> None:
    """The structured contract carries entity-level physical schema facts."""
    from quadkit.contracts.cli.parsers import EntitySpec, FieldSpec, IndexSpec

    spec = EntitySpec(
        name="order",
        table_name="orders",
        fields=(
            FieldSpec(
                name="post_id",
                type="uuid",
                fk="posts.id",
                on_delete="cascade",
            ),
            FieldSpec(name="title", type="str", indexed=True),
        ),
        indexes=(IndexSpec(columns=("post_id", "title"), unique=True),),
        soft_delete=True,
    )

    path = _generate(tmp_path, entity_spec=spec)
    source = path.read_text()
    recorder = _run_upgrade(path)

    assert recorder.tables["orders"] == [
        "id",
        "created_at",
        "updated_at",
        "post_id",
        "title",
        "deleted_at",
    ]
    assert 'ondelete="CASCADE"' in source
    assert ("ix_orders_title", "orders", ("title",)) in recorder.indexes
    assert (
        "ix_orders_post_id_title",
        "orders",
        ("post_id", "title"),
    ) in recorder.indexes
    # The leading composite already covers post_id, so no duplicate FK index.
    assert ("ix_orders_post_id", "orders", ("post_id",)) not in recorder.indexes


def test_structured_spec_rejects_identity_disagreement(tmp_path: Path) -> None:
    """A structured spec cannot quietly describe a different table."""
    from quadkit.contracts.cli.parsers import EntitySpec, FieldSpec

    spec = EntitySpec(
        name="order",
        table_name="purchases",
        fields=(FieldSpec(name="title", type="str"),),
    )

    with pytest.raises(ValueError, match="disagrees with entity_spec table"):
        _generate(tmp_path, entity_spec=spec)
