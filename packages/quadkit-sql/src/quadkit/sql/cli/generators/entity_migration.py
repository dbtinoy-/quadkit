"""Chained alembic migration generator for generated entities."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from quadkit.contracts.cli.generators import (
    GenerationResult,
    derived_index_name,
    foreign_key_constraint_name,
    pluralize_identifier,
    resolve_options,
)
from quadkit.contracts.cli.parsers import (
    EntitySpec,
    FieldSpec,
    IndexSpec,
    resolve_field_specs,
)
from quadkit.sql.cli.generators.base import GeneratorBase
from quadkit.sql.cli.generators.type_map import sa_type

_ON_DELETE_SQL: dict[str, str] = {
    "cascade": "CASCADE",
    "restrict": "RESTRICT",
    "set_null": "SET NULL",
    "no_action": "NO ACTION",
}


@dataclass(frozen=True, slots=True)
class _RenderedIndex:
    name: str
    columns: tuple[str, ...]
    unique: bool = False


def _derived_index_name(table: str, columns: tuple[str, ...]) -> str:
    return derived_index_name(table, columns)


class EntityMigrationGenerator(GeneratorBase):
    """Generate an alembic revision creating the entity's table."""

    name = "migration"
    description = "Generate a chained alembic migration for an entity"
    supports_entity_spec = True

    #: Columns the template always creates. A declared field with one of these
    #: names is the *same* column, not a second one — the model generator
    #: filters the same names, and rendering both would emit a migration whose
    #: ``create_table`` lists ``id`` twice (alembic: duplicate column).
    RESERVED_FIELDS: frozenset[str] = frozenset({"id", "created_at", "updated_at"})

    def generate(
        self,
        name: str,
        fields_str: str | None = None,
        *,
        entity_spec: EntitySpec | None = None,
        rev_id: str = "001",
        prev_rev: str | None = None,
        table_name: str | None = None,
        **options: Any,
    ) -> GenerationResult:
        output_dir = options.pop("output_dir", None)
        if output_dir is not None:
            self.output_dir = Path(str(output_dir)).resolve()

        if entity_spec is not None:
            if self._to_snake_case(entity_spec.name) != self._to_snake_case(name):
                raise ValueError(
                    f"entity_spec.name {entity_spec.name!r} does not match "
                    f"generator name {name!r}"
                )
            if table_name is not None and table_name != entity_spec.table_name:
                raise ValueError(
                    f"table_name {table_name!r} disagrees with entity_spec "
                    f"table {entity_spec.table_name!r}"
                )

        all_fields = resolve_field_specs(fields_str, entity_spec)
        for field in all_fields:
            if field.name in self.RESERVED_FIELDS and field.fk is not None:
                raise ValueError(
                    f"Reserved column {field.name!r} cannot carry a foreign "
                    "key in the entity migration template"
                )
        parsed = [
            field for field in all_fields if field.name not in self.RESERVED_FIELDS
        ]
        table = table_name or (
            entity_spec.table_name
            if entity_spec is not None
            else pluralize_identifier(name)
        )

        column_lines = [self._column_line(field, table) for field in parsed]
        if (
            entity_spec is not None
            and entity_spec.soft_delete
            and all(field.name != "deleted_at" for field in all_fields)
        ):
            column_lines.append(
                'sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),'
            )

        indexes = self._rendered_indexes(
            table=table,
            all_fields=all_fields,
            authored=entity_spec.indexes if entity_spec is not None else (),
            soft_delete=entity_spec.soft_delete if entity_spec is not None else False,
        )
        index_lines = [self._create_index_line(index, table) for index in indexes]
        index_drop_lines = [
            f"op.drop_index({index.name!r}, table_name={table!r})" for index in indexes
        ]

        content = self.render_template(
            "entity_migration.py.jinja2",
            {
                "rev_id": rev_id,
                "prev_rev": prev_rev,
                "table": table,
                "column_lines": column_lines,
                "index_lines": index_lines,
                "index_drop_lines": index_drop_lines,
            },
        )

        file_path = self.output_dir / f"{rev_id}_create_{table}.py"
        self.stage(file_path, content)
        return self.finalize(self.commit(resolve_options(**options)))

    @staticmethod
    def _column_line(field: FieldSpec, table: str) -> str:
        args = [f"sa.{sa_type(field.type)}"]
        if field.fk is not None:
            target_table = field.fk.split(".", 1)[0]
            constraint_name = foreign_key_constraint_name(
                table, field.name, target_table
            )
            fk_args = [
                f'"{field.fk}"',
                f'name="{constraint_name}"',
            ]
            if field.on_delete is not None:
                fk_args.append(f'ondelete="{_ON_DELETE_SQL[field.on_delete]}"')
            args.append(f"sa.ForeignKey({', '.join(fk_args)})")
        args.append(f"nullable={'False' if field.required else 'True'}")
        if field.unique:
            args.append("unique=True")
        return f'sa.Column("{field.name}", {", ".join(args)}),'

    @staticmethod
    def _create_index_line(index: _RenderedIndex, table: str) -> str:
        columns = ", ".join(repr(column) for column in index.columns)
        line = f"op.create_index({index.name!r}, {table!r}, [{columns}]"
        if index.unique:
            line += ", unique=True"
        return line + ")"

    @classmethod
    def _rendered_indexes(
        cls,
        *,
        table: str,
        all_fields: tuple[FieldSpec, ...],
        authored: tuple[IndexSpec, ...],
        soft_delete: bool,
    ) -> tuple[_RenderedIndex, ...]:
        valid_columns = {field.name for field in all_fields} | set(cls.RESERVED_FIELDS)
        if soft_delete:
            valid_columns.add("deleted_at")
        field_by_name = {field.name: field for field in all_fields}
        unique_columns = {field.name for field in all_fields if field.unique}

        rendered: list[_RenderedIndex] = []
        seen_columns: set[tuple[str, ...]] = set()
        by_name: dict[str, _RenderedIndex] = {}

        def add(columns: tuple[str, ...], *, unique: bool, name: str | None) -> None:
            if columns in seen_columns:
                return
            index_name = name or _derived_index_name(table, columns)
            candidate = _RenderedIndex(name=index_name, columns=columns, unique=unique)
            existing = by_name.get(index_name)
            if existing is not None and existing != candidate:
                raise ValueError(
                    f"Duplicate index name {index_name!r} for table {table!r}"
                )
            if existing is not None:
                return
            by_name[index_name] = candidate
            seen_columns.add(columns)
            rendered.append(candidate)

        for index in authored:
            unknown = [name for name in index.columns if name not in valid_columns]
            if unknown:
                raise ValueError(
                    f"Index for table {table!r} references unknown "
                    f"column(s): {', '.join(unknown)}"
                )
            if len(index.columns) == 1 and index.columns[0] in unique_columns:
                # The column's unique constraint already supplies the index.
                seen_columns.add(index.columns)
                continue
            add(index.columns, unique=index.unique, name=index.name)

        for field in all_fields:
            if field.indexed and not field.unique:
                add((field.name,), unique=False, name=None)

        leading_columns = {index.columns[0] for index in rendered if index.columns} | {
            columns[0] for columns in seen_columns if columns
        }
        for field in all_fields:
            if field.fk is None or field.unique:
                continue
            if field.name in leading_columns:
                continue
            add((field.name,), unique=False, name=None)
            leading_columns.add(field.name)

        return tuple(rendered)


__all__ = ["EntityMigrationGenerator"]
