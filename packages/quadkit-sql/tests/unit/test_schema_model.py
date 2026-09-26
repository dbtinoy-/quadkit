"""Focused tests for the declarative schema model system."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import pytest

from quadkit.sql.schema.model import (
    BelongsTo,
    Constraint,
    Field,
    FieldType,
    HasMany,
    Index,
    ManyToMany,
    Model,
    ModelMeta,
    _to_snake_case_plural,
    after_create,
    after_delete,
    after_update,
    before_create,
    before_delete,
    before_update,
    fire_hooks,
)


def _value_factory() -> int:
    return 42


class TestField:
    def test_primary_key_forces_non_nullable(self) -> None:
        field = Field(UUID, primary_key=True)
        assert not field.nullable

    def test_unknown_python_type_defaults_to_string(self) -> None:
        field = Field(object)
        assert field.field_type is FieldType.STRING

    def test_db_type_override_wins(self) -> None:
        field = Field(str, db_type="CITEXT")
        assert field.to_sql_type("postgresql") == "CITEXT"

    def test_callable_default_invoked(self) -> None:
        field = Field(int, default=_value_factory)
        assert field.has_default
        assert field.get_default() == 42

    def test_no_default_returns_none(self) -> None:
        assert Field(int).get_default() is None

    @pytest.mark.parametrize(
        ("field_type", "expected"),
        [
            (FieldType.STRING, "VARCHAR(255)"),
            (FieldType.TEXT, "TEXT"),
            (FieldType.INTEGER, "INTEGER"),
            (FieldType.BIGINT, "BIGINT"),
            (FieldType.FLOAT, "DOUBLE PRECISION"),
            (FieldType.DECIMAL, "NUMERIC"),
            (FieldType.BOOLEAN, "BOOLEAN"),
            (FieldType.DATE, "DATE"),
            (FieldType.DATETIME, "TIMESTAMP WITHOUT TIME ZONE"),
            (FieldType.TIMESTAMP, "TIMESTAMP WITH TIME ZONE"),
            (FieldType.UUID, "UUID"),
            (FieldType.JSON, "JSON"),
            (FieldType.JSONB, "JSONB"),
            (FieldType.BINARY, "BYTEA"),
            (FieldType.ARRAY, "TEXT[]"),
        ],
    )
    def test_postgresql_type_map(
        self,
        field_type: FieldType,
        expected: str,
    ) -> None:
        field = Field(str, max_length=255)
        field.field_type = field_type
        assert field.to_sql_type("postgresql") == expected

    @pytest.mark.parametrize(
        ("field_type", "expected"),
        [
            (FieldType.INTEGER, "INT"),
            (FieldType.FLOAT, "DOUBLE"),
            (FieldType.BOOLEAN, "TINYINT(1)"),
            (FieldType.DECIMAL, "DECIMAL"),
            (FieldType.UUID, "CHAR(36)"),
            (FieldType.JSONB, "JSON"),
            (FieldType.BINARY, "BLOB"),
            (FieldType.ARRAY, "JSON"),
            (FieldType.DATETIME, "DATETIME"),
        ],
    )
    def test_mysql_type_map(self, field_type: FieldType, expected: str) -> None:
        field = Field(str)
        field.field_type = field_type
        assert field.to_sql_type("mysql") == expected

    @pytest.mark.parametrize(
        ("field_type", "expected"),
        [
            (FieldType.STRING, "TEXT"),
            (FieldType.INTEGER, "INTEGER"),
            (FieldType.BIGINT, "INTEGER"),
            (FieldType.FLOAT, "REAL"),
            (FieldType.BOOLEAN, "INTEGER"),
            (FieldType.DATE, "TEXT"),
            (FieldType.DATETIME, "TEXT"),
            (FieldType.UUID, "TEXT"),
            (FieldType.JSON, "TEXT"),
            (FieldType.ARRAY, "TEXT"),
        ],
    )
    def test_sqlite_type_map(self, field_type: FieldType, expected: str) -> None:
        field = Field(str)
        field.field_type = field_type
        assert field.to_sql_type("sqlite") == expected

    def test_unknown_dialect_falls_back_to_pg(self) -> None:
        field = Field(bytes)
        assert field.to_sql_type("oracle") == "BYTEA"

    def test_unknown_type_falls_back_to_text(self) -> None:
        field = Field(str)
        field.field_type = "nope"  # type: ignore[assignment]
        assert field.to_sql_type("postgresql") == "TEXT"

    def test_validate_null_on_nullable_ok(self) -> None:
        assert Field(int, nullable=True).validate(None) == []

    def test_validate_null_on_required(self) -> None:
        field = Field(int, nullable=False)
        field.name = "email"
        assert field.validate(None) == ["email: cannot be NULL"]

    def test_validate_exceeds_max_length(self) -> None:
        field = Field(str, max_length=3)
        field.name = "name"
        assert field.validate("abcd") == ["name: exceeds max_length 3"]

    def test_validate_below_min_length(self) -> None:
        field = Field(str, min_length=5, max_length=10)
        field.name = "name"
        assert field.validate("ab") == ["name: below min_length 5"]

    def test_validate_non_string_not_length_checked(self) -> None:
        assert Field(str, max_length=3).validate(12345) == []

    def test_repr(self) -> None:
        text = repr(Field(str, primary_key=True, nullable=False))
        assert "Field(str" in text
        assert "pk=True" in text


class TestIndexAndConstraint:
    def test_string_column_normalized_to_list(self) -> None:
        index = Index("idx_email", "email")
        assert index.columns == ["email"]

    def test_index_sql(self) -> None:
        index = Index("idx_a", ["a", "b"], unique=True)
        assert index.to_sql("tbl") == "CREATE UNIQUE INDEX idx_a ON tbl (a, b)"

    def test_index_sql_with_condition(self) -> None:
        index = Index("idx_p", "p", condition='p > 0')
        assert index.to_sql("tbl") == "CREATE INDEX idx_p ON tbl (p) WHERE p > 0"

    def test_constraint_sql(self) -> None:
        constraint = Constraint("chk_price", "price >= 0")
        assert constraint.to_sql() == "CONSTRAINT chk_price CHECK (price >= 0)"


class TestRelations:
    def test_has_many_defaults(self) -> None:
        rel = HasMany(target="Post", foreign_key="user_id")
        assert rel.local_key == "id"

    def test_belongs_to_defaults(self) -> None:
        rel = BelongsTo(target="User", foreign_key="user_id")
        assert rel.owner_key == "id"

    def test_many_to_many_fields(self) -> None:
        rel = ManyToMany(target="Tag", pivot_table="post_tags", foreign_key="post_id", related_key="tag_id")
        assert rel.pivot_table == "post_tags"


class TestModelMeta:
    def test_tablename_auto_generated(self) -> None:
        class Order(Model):
            pass

        assert Order.__tablename__ == "orders"

    def test_tablename_not_auto_generated_for_base(self) -> None:
        assert Model.__tablename__ == ""

    def test_fields_inherited_from_base(self) -> None:
        class BaseModel(Model):
            id = Field(int, primary_key=True)

        class ChildModel(BaseModel):
            name = Field(str)

        assert "id" in ChildModel.__fields__
        assert ChildModel.__fields__["id"].name == "id"
        assert ChildModel.__fields__["name"].name == "name"

    def test_relations_inherited(self) -> None:
        class BaseModel(Model):
            items = HasMany(target="Item", foreign_key="base_id")

        class ChildModel(BaseModel):
            pass

        assert "items" in ChildModel.__relations__

    def test_meta_options_processed(self) -> None:
        class UserModel(Model):
            class Meta:
                soft_delete = True
                timestamps = True
                multi_tenant = True
                ordering = ["-created_at"]

        assert UserModel.__soft_delete__
        assert UserModel.__timestamps__
        assert UserModel.__multi_tenant__
        assert UserModel.__ordering__ == ["-created_at"]

    def test_no_meta_option_defaults(self) -> None:
        class Plain(Model):
            pass

        assert not getattr(Plain, "__soft_delete__", False)
        assert getattr(Plain, "__ordering__", []) == []


class TestModel:
    def test_init_assigns_kwargs(self) -> None:
        class UserModel(Model):
            name = Field(str)

        model = UserModel(name="alice")
        assert model.name == "alice"

    def test_init_uses_callable_default(self) -> None:
        class WidgetModel(Model):
            count = Field(int, default=_value_factory)

        assert WidgetModel().count == 42

    def test_init_missing_field_is_none(self) -> None:
        class SimpleModel(Model):
            note = Field(str)

        assert SimpleModel().note is None

    def test_to_dict(self) -> None:
        class UserModel(Model):
            name = Field(str)

        assert UserModel(name="alice").to_dict() == {"name": "alice"}

    def test_model_validate_aggregates_field_errors(self) -> None:
        class UserModel(Model):
            name = Field(str, min_length=4)

        assert UserModel(name="ab").validate() == ["name: below min_length 4"]

    def test_model_validate_clean(self) -> None:
        class UserModel(Model):
            name = Field(str)

        assert UserModel(name="ok").validate() == []

    def test_get_primary_key_field(self) -> None:
        class UserModel(Model):
            id = Field(int, primary_key=True)
            name = Field(str)

        assert UserModel.get_primary_key_field() == "id"

    def test_get_primary_key_field_none(self) -> None:
        class NoPkModel(Model):
            name = Field(str)

        assert NoPkModel.get_primary_key_field() is None

    def test_get_column_names(self) -> None:
        class UserModel(Model):
            id = Field(int, primary_key=True)
            name = Field(str)

        assert UserModel.get_column_names() == ["id", "name"]

    def test_get_foreign_keys(self) -> None:
        class UserModel(Model):
            dept_id = Field(int, foreign_key="departments.id")

        assert UserModel.get_foreign_keys() == {"dept_id": "departments.id"}

    def test_repr_with_pk(self) -> None:
        class UserModel(Model):
            id = Field(int, primary_key=True)

        assert repr(UserModel(id=7)) == "<UserModel id=7>"

    def test_repr_without_pk(self) -> None:
        class NoPkModel(Model):
            name = Field(str)

        assert repr(NoPkModel()) == "<NoPkModel None=?>"


class TestCreateTableSql:
    def test_string_default_quoted(self) -> None:
        class UserModel(Model):
            status = Field(str, default="active")

        assert "DEFAULT 'active'" in UserModel.generate_create_table_sql()

    def test_bool_default(self) -> None:
        class FlagModel(Model):
            active = Field(bool, default=True)

        assert "DEFAULT TRUE" in FlagModel.generate_create_table_sql()

    def test_int_default_unquoted(self) -> None:
        class CountModel(Model):
            count = Field(int, default=3)

        assert "DEFAULT 3" in CountModel.generate_create_table_sql()

    def test_false_default(self) -> None:
        class FlagModel(Model):
            active = Field(bool, default=False)

        assert "DEFAULT FALSE" in FlagModel.generate_create_table_sql()

    def test_callable_default_not_inlined(self) -> None:
        class GenModel(Model):
            token = Field(str, default=_value_factory)

        assert "DEFAULT" not in GenModel.generate_create_table_sql()

    def test_not_null_and_unique_and_references_and_check(self) -> None:
        class OrderModel(Model):
            user_id = Field(
                int,
                nullable=False,
                unique=True,
                foreign_key="users.id",
                check="user_id > 0",
            )

        sql = OrderModel.generate_create_table_sql()
        assert "NOT NULL" in sql
        assert "UNIQUE" in sql
        assert "REFERENCES users(id)" in sql
        assert "CHECK (user_id > 0)" in sql

    def test_composite_primary_key(self) -> None:
        class CompositeModel(Model):
            a = Field(str, primary_key=True)
            b = Field(str, primary_key=True)

        assert "PRIMARY KEY (a, b)" in CompositeModel.generate_create_table_sql()

    def test_constraints_appended(self) -> None:
        class CheckedModel(Model):
            price = Field(int)
            __constraints__ = [Constraint("chk_price", "price >= 0")]

        assert "CONSTRAINT chk_price CHECK (price >= 0)" in (
            CheckedModel.generate_create_table_sql()
        )

    def test_mysql_dialect_type(self) -> None:
        class NumModel(Model):
            count = Field(int)

        assert "INT" in NumModel.generate_create_table_sql("mysql")


class TestSnakeCase:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("User", "users"),
            ("Post", "posts"),
            ("Category", "categories"),
            ("Box", "boxes"),
            ("Watch", "watches"),
            ("Fox", "foxes"),
            ("Address", "addresses"),
            ("OrderItem", "order_items"),
        ],
    )
    def test_pluralization(self, name: str, expected: str) -> None:
        assert _to_snake_case_plural(name) == expected


class TestHooks:
    def test_decorators_set_event(self) -> None:
        @before_create
        def h1() -> None: ...

        @after_create
        def h2() -> None: ...

        @before_update
        def h3() -> None: ...

        @after_update
        def h4() -> None: ...

        @before_delete
        def h5() -> None: ...

        @after_delete
        def h6() -> None: ...

        assert h1._hook_event == "before_create"
        assert h2._hook_event == "after_create"
        assert h3._hook_event == "before_update"
        assert h4._hook_event == "after_update"
        assert h5._hook_event == "before_delete"
        assert h6._hook_event == "after_delete"

    def test_fire_hooks_sync_and_async(self) -> None:
        from quadkit.sql.schema.model import _model_hooks

        calls: list[str] = []

        def sync_hook(entity: object) -> None:
            calls.append(f"sync-{entity}")

        async def async_hook(entity: object) -> None:
            calls.append(f"async-{entity}")

        _model_hooks["widget"] = {
            "before_create": [sync_hook, async_hook],
        }
        try:
            import asyncio

            asyncio.run(fire_hooks("widget", "before_create", "w"))
        finally:
            del _model_hooks["widget"]
        assert calls == ["sync-w", "async-w"]

    def test_fire_hooks_no_handlers(self) -> None:
        import asyncio

        assert asyncio.run(fire_hooks("ghost", "before_create", None)) is None